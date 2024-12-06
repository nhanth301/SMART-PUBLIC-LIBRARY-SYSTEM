import torch
import torch.nn as nn
import torch.nn.functional as F

class PolicyNetwork(nn.Module):
    def __init__(self, embedding_dim, action_dim, hidden_dim=256):
        super(PolicyNetwork, self).__init__()
        
        # Constants for reward types
        self.REWARD_SKIP = -1
        self.REWARD_VIEW = 1
        self.REWARD_READ = 2
        
        # Reward embedding layer
        self.reward_embedding = nn.Embedding(3, embedding_dim)  # 3 categories: skip, view, read
        
        # State Encoder components
        self.state_encoder = nn.ModuleDict({
            'attention': nn.Sequential(
                nn.Linear(embedding_dim * 2, hidden_dim),  # embedding + reward_embedding
                nn.Tanh(),
                nn.Linear(hidden_dim, 1)
            ),
            'interaction_encoder': nn.Sequential(
                nn.Linear(embedding_dim * 2, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, embedding_dim)
            ),
            'context_encoder': nn.Sequential(
                nn.Linear(embedding_dim * 3, hidden_dim),  # weighted_sum + recent + interaction
                nn.ReLU(),
                nn.Linear(hidden_dim, embedding_dim)
            )
        })

        # Policy network component
        self.policy_layers = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim)
        )

        self.embedding_dim = embedding_dim

    def _convert_reward_to_index(self, reward):
        """Convert numerical reward to embedding index"""
        if reward == self.REWARD_VIEW:
            return 1
        elif reward == self.REWARD_READ:
            return 2
        else: 
            return 0

    def encode_state(self, embeddings, rewards):
        if len(embeddings) == 0:
            return torch.zeros(self.embedding_dim)

        embeddings = torch.stack(embeddings)
        
        # Convert rewards to indices for embedding
        reward_indices = torch.tensor([self._convert_reward_to_index(r) for r in rewards])
        reward_embeddings = self.reward_embedding(reward_indices)

        # Concatenate item embeddings with reward embeddings
        combined_embeddings = torch.cat([embeddings, reward_embeddings], dim=1)
        
        # Calculate attention scores
        attention_scores = self.state_encoder['attention'](combined_embeddings)

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
        return F.softmax(self.policy_layers(state), dim=-1)