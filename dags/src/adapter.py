import random
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import LambdaLR
from torch.nn.utils import clip_grad_norm_
import torch.nn.functional as F
import pandas as pd
import json

class LinearAdapter(nn.Module):
    def __init__(self, input_dim, output_dim):
        super().__init__()
        self.linear = nn.Linear(input_dim, output_dim)

    def forward(self, x):
        return self.linear(x)
    

class TripletDataset(Dataset):
    def __init__(self, data):
        self.anchors = data["anchor"].values
        self.positives = data["pos"].values
        self.negatives = data["neg"].values

    def __len__(self):
        return len(self.anchors)

    def __getitem__(self, idx):
        anchor = torch.tensor(json.loads(self.anchors[idx]))
        pos = torch.tensor(json.loads(self.positives[idx]))
        neg = torch.tensor(json.loads(self.negatives[idx]))
           
        return anchor, pos, neg

def get_linear_schedule_with_warmup(optimizer, num_warmup_steps, num_training_steps):
    def lr_lambda(current_step):
        if current_step < num_warmup_steps:
            return float(current_step) / float(max(1, num_warmup_steps))
        return max(0.0, float(num_training_steps - current_step) / float(max(1, num_training_steps - num_warmup_steps)))
    return LambdaLR(optimizer, lr_lambda)

def train_linear_adapter(train_data, num_epochs=10, batch_size=32, 
                         learning_rate=2e-5, warmup_steps=100, max_grad_norm=1.0, margin=1.0, input_dim=768, output_dim=128):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    adapter = LinearAdapter(input_dim,output_dim).to(device)

    triplet_loss = nn.TripletMarginWithDistanceLoss(distance_function=lambda x, y: 1.0 - F.cosine_similarity(x, y), margin=margin)
    optimizer = AdamW(adapter.parameters(), lr=learning_rate)

    dataset = TripletDataset(train_data)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    total_steps = len(dataloader) * num_epochs
    
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps)
    losses = []
    
    for epoch in range(num_epochs):
        total_loss = 0
        for batch in dataloader:
            anchor_emb, positive_emb, negative_emb = [x.to(device) for x in batch]
            
            # Forward pass
            adapted_anchor_emb = adapter(anchor_emb)
            adapted_pos_emb = adapter(positive_emb)
            adapted_neg_emb = adapter(negative_emb)
            
            # Compute loss
            loss = triplet_loss(adapted_anchor_emb, adapted_pos_emb, adapted_neg_emb)
            
            # Backward pass and optimization
            optimizer.zero_grad()
            loss.backward()
            
            # Gradient clipping
            clip_grad_norm_(adapter.parameters(), max_grad_norm)
            
            optimizer.step()
            scheduler.step()
            
            total_loss += loss.item()
        
        l = total_loss/len(dataloader)
        print(f"Epoch {epoch+1}/{num_epochs}, Loss: {l:.4f}")
        losses.append(l)

    return adapter, losses


