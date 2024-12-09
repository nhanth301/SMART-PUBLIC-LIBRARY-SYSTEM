import torch
from src.utils import train_reinforce, create_batch
import random
random.seed(42)
torch.manual_seed(42)
book_embeddings = [torch.tensor([0.1000, 0.2000]), torch.tensor([0.3000, 0.4000]), torch.tensor([0.5000, 0.6000]), torch.tensor([0.9651, 0.5216]), torch.tensor([0.5984, 0.9511]), torch.tensor([0.1893, 0.9825]), torch.tensor([0.5432, 0.8718]), torch.tensor([0.7118, 0.6313]), torch.tensor([0.2358, 0.6915]), torch.tensor([0.3728, 0.2477]), torch.tensor([0.8413, 0.7165]), torch.tensor([0.4819, 0.6806]), torch.tensor([0.4537, 0.6283]), torch.tensor([0.9662, 0.3566]), torch.tensor([0.4381, 0.3451]), torch.tensor([0.6051, 0.6803]), torch.tensor([0.8833, 0.9616]), torch.tensor([0.6038, 0.4617]), torch.tensor([0.9537, 0.9744]), torch.tensor([0.2278, 0.7901])]


# if __name__ == "__main__":
#     embedding_dim = len(book_embeddings[0])
#     action_dim = 20 
#     window_size = 3
#     history_batches = generate_test_data(book_embeddings)
#     states, actions, rewards = create_batch(history_batches,book_embeddings,window_size)
#     agent = train_reinforce(states, actions, rewards, embedding_dim, action_dim)

def train(ui_history, embeddings, window_size=5, epochs=100, pretrained_weights=None, pretrained_optim=None):
    embedding_dim = len(embeddings[0])
    action_dim = len(embeddings) 
    states, reward_states, actions, rewards = create_batch(ui_history,embeddings,window_size)
    agent, losses = train_reinforce(states, reward_states, actions, rewards, embedding_dim, action_dim, epochs, pretrained_weights, pretrained_optim)
    return agent.policy.state_dict(), agent.optimizer.state_dict(), losses
