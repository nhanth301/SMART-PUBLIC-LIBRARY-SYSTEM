import torch
import random
from src.reinforce import REINFORCE
def create_dynamic_state_vectors(session_history, book_embeddings, window_size):
    states = []
    reward_states = []
    actions = []
    rewards = []

    for i in range(len(session_history)):
        start_idx = max(0, i - window_size)
        current_history = session_history[start_idx:i]
        embeddings = [book_embeddings[item[0]] for item in current_history]
        reward_state = [item[1] for item in current_history]
        states.append(embeddings)
        reward_states.append(reward_state)
        actions.append(session_history[i][0])
        rewards.append(session_history[i][1])

    return states, reward_states, torch.tensor(actions), torch.tensor(rewards)


def create_batch(history_batches, book_embeddings, window_size):
    states_batches = []
    reward_states_batches = []
    action_batches = []
    rewards_batches = []
    for session_history in history_batches:
        states, reward_states, actions, rewards = create_dynamic_state_vectors(session_history, book_embeddings, window_size)
        states_batches.append(states)
        reward_states_batches.append(reward_states)
        action_batches.append(actions)
        rewards_batches.append(rewards)
    return states_batches, reward_states_batches, action_batches, rewards_batches


def train_reinforce(states, reward_states, actions, rewards, embedding_dim, action_dim, epochs=100, pretrained_weights=None, pretrained_optim=None):
    agent = REINFORCE(embedding_dim, action_dim)
    if pretrained_weights and pretrained_optim:
        agent.load_model_from_dict(pretrained_weights, pretrained_optim)

    num_epochs = epochs
    losses = []
    for epoch in range(num_epochs):
        loss = agent.update(states, reward_states, actions, rewards)
        losses.append(loss)
        print(f"Epoch {epoch + 1}/{num_epochs}, Loss: {loss:.4f}")
    return agent, losses


