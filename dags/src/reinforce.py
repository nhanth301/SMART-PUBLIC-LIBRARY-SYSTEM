import torch
import numpy as np
import torch.optim as optim
import json
from src.policy_network import PolicyNetwork
from torch.optim.lr_scheduler import ReduceLROnPlateau

class REINFORCE:
    def __init__(self, embedding_dim, action_dim, lr=0.001):
        self.policy = PolicyNetwork(embedding_dim, action_dim)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=lr)
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=5,
            min_lr=1e-6,
            verbose=True
        )

    def select_action(self, embeddings, timestamps=None, mask=None):
        probs = self.policy(embeddings, timestamps, mask)

        m = torch.distributions.Categorical(probs)
        action = m.sample()

        return action, m.log_prob(action)

    def update(self, batch_states, batch_reward_states, batch_actions, batch_rewards, batch_size=32):
        n_sessions = len(batch_states)
        indices = torch.randperm(n_sessions)
        total_loss = 0
        entropy_weight = 0.01 

        for start_idx in range(0, n_sessions, batch_size):
            policy_loss = []
            entropy_loss = []
            end_idx = min(start_idx + batch_size, n_sessions)
            batch_indices = indices[start_idx:end_idx]

            for idx in batch_indices:
                session_embeddings = batch_states[idx]
                session_reward_states = batch_reward_states[idx]
                session_actions = batch_actions[idx]
                session_rewards = batch_rewards[idx].float()

                log_probs = []
                batch_entropy = []
                
                for embeddings, action, rewards in zip(session_embeddings, session_actions, session_reward_states):
                    probs = self.policy(embeddings, rewards)
                    dist = torch.distributions.Categorical(probs)
                    log_prob = dist.log_prob(action)
                    entropy = dist.entropy()
                    
                    log_probs.append(log_prob)
                    batch_entropy.append(entropy)

                log_probs = torch.stack(log_probs)
                batch_entropy = torch.stack(batch_entropy)
                
                if len(session_rewards) > 1:
                    session_rewards = (session_rewards - session_rewards.mean()) / (session_rewards.std() + 1e-8)
                
                discounted_rewards = []
                running_reward = 0
                gamma = 0.99
                for r in reversed(session_rewards.cpu().numpy()):
                    running_reward = r + gamma * running_reward
                    discounted_rewards.insert(0, running_reward)
                discounted_rewards = torch.tensor(discounted_rewards, dtype=torch.float32, device=log_probs.device)

                policy_loss_value = -(log_probs * discounted_rewards).sum()
                entropy_loss_value = -batch_entropy.mean() * entropy_weight
                
                policy_loss.append(policy_loss_value)
                entropy_loss.append(entropy_loss_value)

            batch_policy_loss = torch.stack(policy_loss).mean()
            batch_entropy_loss = torch.stack(entropy_loss).mean()
            batch_loss = batch_policy_loss + batch_entropy_loss
            
            total_loss += batch_loss.item()

            self.optimizer.zero_grad()
            batch_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy.parameters(), max_norm=1.0)
            self.optimizer.step()

        avg_loss = total_loss / n_sessions
        self.scheduler.step(avg_loss)
        
        return avg_loss

    
    def save_model(self, filename):
        # Lưu các trọng số của mô hình trừ lớp policy_layers cuối cùng
        model_state_dict = self.policy.state_dict()
        
        # Lưu các trọng số
        torch.save(model_state_dict, filename)

    def load_model(self, filename):
        model_state_dict = torch.load(filename, weights_only=True)
        try:
            self.policy.load_state_dict(model_state_dict)
        except RuntimeError:
            policy_state_dict = {k: v for k, v in model_state_dict.items() if 'policy_layers.2' not in k}
            self.policy.load_state_dict(policy_state_dict, strict=False)
    
    def save_model_as_json(self, filename):
        model_state_dict = self.policy.state_dict()

        model_state_dict = {k: v.cpu().numpy().tolist() for k, v in model_state_dict.items()}

        with open(filename, 'w') as f:
            json.dump(model_state_dict, f) 
    
    def load_model_from_json(self, filename):
        with open(filename, 'r') as f:
            model_state_dict = json.load(f)
        model_state_dict = {k: torch.tensor(np.array(v)) for k, v in model_state_dict.items()}
        try:
            self.policy.load_state_dict(model_state_dict)
        except RuntimeError:
            policy_state_dict = {k: v for k, v in model_state_dict.items() if 'policy_layers.2' not in k}
            self.policy.load_state_dict(policy_state_dict, strict=False)
    
    def load_model_from_dict(self, state_dict, optim_dict):
        def convert_lists_to_tensors(d):
            if isinstance(d, list):
                try:
                    # Thêm device nếu cần
                    return torch.tensor(np.array(d, dtype=np.float32))
                except:
                    # Xử lý trường hợp không thể chuyển đổi trực tiếp
                    return [convert_lists_to_tensors(item) for item in d]
            elif isinstance(d, dict):
                return {k: convert_lists_to_tensors(v) for k, v in d.items()}
            elif isinstance(d, torch.Tensor):
                return d
            elif isinstance(d, np.ndarray):
                return torch.from_numpy(d)
            else:
                return d
        model_state_dict = {k: torch.tensor(np.array(v)) for k, v in state_dict.items()}
        optim_state_dict = convert_lists_to_tensors(optim_dict)
        try:
            self.policy.load_state_dict(model_state_dict)
        except RuntimeError:
            policy_state_dict = {k: v for k, v in model_state_dict.items() if 'policy_layers.2' not in k}
            self.policy.load_state_dict(policy_state_dict, strict=False)
            self.optimizer.load_state_dict(optim_state_dict,strict=False)