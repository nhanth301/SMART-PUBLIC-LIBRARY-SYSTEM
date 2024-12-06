import torch
import torch.nn as nn
import torch.nn.functional as F

class PolicyNetwork(nn.Module):
    def __init__(self, embedding_dim, action_dim, hidden_dim=256):
        super(PolicyNetwork, self).__init__()
        
        self.REWARD_SKIP = -1.0
        self.REWARD_VIEW = 1.0
        self.REWARD_READ = 2.0
        
        self.reward_embedding = nn.Embedding(3, embedding_dim)
        
        nn.init.xavier_uniform_(self.reward_embedding.weight)
        
        self.state_encoder = nn.ModuleDict({
            'attention': nn.Sequential(
                nn.Linear(embedding_dim * 2, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, 1)
            ),
            'interaction_encoder': nn.Sequential(
                nn.Linear(embedding_dim * 2, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, embedding_dim)
            ),
            'context_encoder': nn.Sequential(
                nn.Linear(embedding_dim * 3, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, embedding_dim)
            )
        })

        self.policy_layers = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, action_dim)
        )

        self.embedding_dim = embedding_dim

    def _convert_reward_to_index(self, reward):
        if reward == self.REWARD_VIEW:
            return 1
        elif reward == self.REWARD_READ:
            return 2
        else: 
            return 0

    def encode_state(self, embeddings, rewards):
        if len(embeddings) == 0:
            return torch.zeros(self.embedding_dim, device=self.reward_embedding.weight.device)

        embeddings = torch.stack(embeddings)
        
        # Convert rewards to indices for embedding
        reward_indices = torch.tensor([self._convert_reward_to_index(r) for r in rewards],
                                    device=embeddings.device)
        reward_embeddings = self.reward_embedding(reward_indices)

        # Concatenate item embeddings with reward embeddings
        combined_embeddings = torch.cat([embeddings, reward_embeddings], dim=1)
        
        # Calculate attention scores
        attention_scores = self.state_encoder['attention'](combined_embeddings)
        attention_scores = F.layer_norm(attention_scores, attention_scores.shape)
        
        # Normalize attention scores
        attention_weights = F.softmax(attention_scores, dim=0)

        # Weighted sum of embeddings
        weighted_sum = (embeddings * attention_weights).sum(dim=0)

        # Get the most recent embedding and reward
        recent_embedding = embeddings[-1]
        recent_reward_embedding = reward_embeddings[-1]

        # Encode interaction context
        interaction_context = self.state_encoder['interaction_encoder'](
            torch.cat([recent_embedding, recent_reward_embedding])
        )

        # Combine all contexts
        combined = torch.cat([weighted_sum, recent_embedding, interaction_context])
        state = self.state_encoder['context_encoder'](combined)

        return state

    def forward(self, embeddings, rewards):
        state = self.encode_state(embeddings, rewards)
        logits = self.policy_layers(state)
        return F.softmax(logits, dim=-1)