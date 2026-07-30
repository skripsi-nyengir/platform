"""Vendored trained-model architectures for artifact inference.

Reconstructions are copied verbatim from the validated offline harness so the
in-platform forward pass reproduces each checkpoint's stored reconstruction
within 1e-3 (Gate A). Do not "clean up" the forward math: parity is the contract.
"""
from __future__ import annotations

from typing import Any, cast

import torch
from torch import nn

# Trained-model architectures (window 10), copied verbatim from the step8 final
# roster. Forward math is byte-faithful to the checkpoints; do not refactor it
# (Gate A parity is the contract).
class Conv1dAutoencoder(nn.Module):
    def __init__(self, input_channels: int = 2, latent_channels: int = 16) -> None:
        super().__init__()
        self.input_channels = int(input_channels)
        self.encoder = nn.Sequential(
            nn.Conv1d(input_channels, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 32, 3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv1d(32, latent_channels, 3, stride=2, padding=1),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose1d(latent_channels, 32, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.ConvTranspose1d(32, 16, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, input_channels, 3, padding=1),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        length = inputs.shape[1]
        encoded = self.encoder(
            torch.nn.functional.pad(inputs.transpose(1, 2), (0, (-length) % 4))
        )
        return cast(torch.Tensor, self.decoder(encoded)[..., :length].transpose(1, 2))


class LstmEncoder(nn.Module):
    def __init__(
        self, input_channels: int, hidden_size: int, latent_size: int, num_layers: int, dropout: float
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_channels,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.to_latent = nn.Linear(hidden_size, latent_size)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        _, (hidden, _) = self.lstm(inputs)
        return cast(torch.Tensor, self.to_latent(hidden[-1]))


class LstmDecoder(nn.Module):
    def __init__(
        self, latent_size: int, hidden_size: int, output_channels: int, num_layers: int, dropout: float
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=latent_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.to_output = nn.Linear(hidden_size, output_channels)

    def forward(self, context: torch.Tensor, sequence_length: int) -> torch.Tensor:
        repeated = context.unsqueeze(1).expand(-1, sequence_length, -1)
        decoded, _ = self.lstm(repeated)
        return cast(torch.Tensor, self.to_output(decoded))


class LstmAutoencoder(nn.Module):
    def __init__(
        self,
        input_channels: int = 2,
        hidden_size: int = 32,
        latent_size: int = 8,
        num_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.input_channels = int(input_channels)
        self.encoder = LstmEncoder(
            input_channels, hidden_size, latent_size, num_layers, dropout
        )
        self.decoder = LstmDecoder(
            latent_size, hidden_size, input_channels, num_layers, dropout
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        reconstruction = self.decoder(self.encoder(inputs), inputs.shape[1])
        return cast(torch.Tensor, reconstruction)


class TransformerAutoencoder(nn.Module):
    def __init__(
        self,
        input_channels: int = 2,
        d_model: int = 32,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 64,
        dropout: float = 0.1,
        window_size: int = 10,
    ) -> None:
        super().__init__()
        self.input_channels = int(input_channels)
        self.window_size = int(window_size)
        self.input_projection = nn.Linear(input_channels, d_model)
        self.position_embedding = nn.Parameter(torch.zeros(1, window_size, d_model))
        self.transformer = nn.Transformer(
            d_model=d_model,
            nhead=nhead,
            num_encoder_layers=num_layers,
            num_decoder_layers=num_layers,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.output_projection = nn.Linear(d_model, input_channels)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        embeddings = self.input_projection(inputs) + self.position_embedding[:, : inputs.shape[1]]
        return cast(torch.Tensor, self.output_projection(self.transformer(embeddings, embeddings)))


# Recurrent autoencoders (window 10). Forward math is byte-faithful to the step8
# checkpoints; do not refactor it (Gate A parity is the contract).
class RnnEncoder(nn.Module):
    def __init__(
        self,
        input_channels: int,
        hidden_size: int,
        latent_size: int,
        num_layers: int,
        dropout: float,
        nonlinearity: str,
    ) -> None:
        super().__init__()
        self.recurrent = nn.RNN(
            input_size=input_channels,
            hidden_size=hidden_size,
            num_layers=num_layers,
            nonlinearity=nonlinearity,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.to_latent = nn.Linear(hidden_size, latent_size)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        _, hidden = self.recurrent(inputs)
        return cast(torch.Tensor, self.to_latent(hidden[-1]))


class RnnDecoder(nn.Module):
    def __init__(
        self,
        latent_size: int,
        hidden_size: int,
        output_channels: int,
        num_layers: int,
        dropout: float,
        nonlinearity: str,
    ) -> None:
        super().__init__()
        self.recurrent = nn.RNN(
            input_size=latent_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            nonlinearity=nonlinearity,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.to_output = nn.Linear(hidden_size, output_channels)

    def forward(self, context: torch.Tensor, sequence_length: int) -> torch.Tensor:
        repeated = context.unsqueeze(1).expand(-1, sequence_length, -1)
        decoded, _ = self.recurrent(repeated)
        return cast(torch.Tensor, self.to_output(decoded))


class RnnAutoencoder(nn.Module):
    def __init__(
        self,
        input_channels: int = 2,
        hidden_size: int = 32,
        latent_size: int = 8,
        num_layers: int = 2,
        dropout: float = 0.1,
        nonlinearity: str = "tanh",
    ) -> None:
        super().__init__()
        self.input_channels = int(input_channels)
        self.encoder = RnnEncoder(
            input_channels, hidden_size, latent_size, num_layers, dropout, nonlinearity
        )
        self.decoder = RnnDecoder(
            latent_size, hidden_size, input_channels, num_layers, dropout, nonlinearity
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        reconstruction = self.decoder(self.encoder(inputs), inputs.shape[1])
        return cast(torch.Tensor, reconstruction)


class GruEncoder(nn.Module):
    def __init__(
        self,
        input_channels: int,
        hidden_size: int,
        latent_size: int,
        num_layers: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.recurrent = nn.GRU(
            input_size=input_channels,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.to_latent = nn.Linear(hidden_size, latent_size)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        _, hidden = self.recurrent(inputs)
        return cast(torch.Tensor, self.to_latent(hidden[-1]))


class GruDecoder(nn.Module):
    def __init__(
        self,
        latent_size: int,
        hidden_size: int,
        output_channels: int,
        num_layers: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.recurrent = nn.GRU(
            input_size=latent_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.to_output = nn.Linear(hidden_size, output_channels)

    def forward(self, context: torch.Tensor, sequence_length: int) -> torch.Tensor:
        repeated = context.unsqueeze(1).expand(-1, sequence_length, -1)
        decoded, _ = self.recurrent(repeated)
        return cast(torch.Tensor, self.to_output(decoded))


class GruAutoencoder(nn.Module):
    def __init__(
        self,
        input_channels: int = 2,
        hidden_size: int = 32,
        latent_size: int = 8,
        num_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.input_channels = int(input_channels)
        self.encoder = GruEncoder(
            input_channels, hidden_size, latent_size, num_layers, dropout
        )
        self.decoder = GruDecoder(
            latent_size, hidden_size, input_channels, num_layers, dropout
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        reconstruction = self.decoder(self.encoder(inputs), inputs.shape[1])
        return cast(torch.Tensor, reconstruction)


def _load_lstm(state_dict: dict[str, Any]) -> nn.Module:
    model = LstmAutoencoder()
    model.load_state_dict(state_dict, strict=True)
    return model


def _load_conv1d(state_dict: dict[str, Any]) -> nn.Module:
    model = Conv1dAutoencoder()
    model.load_state_dict(state_dict, strict=True)
    return model


def _load_transformer(state_dict: dict[str, Any]) -> nn.Module:
    model = TransformerAutoencoder()
    model.load_state_dict(state_dict, strict=True)
    return model


def _load_rnn(state_dict: dict[str, Any]) -> nn.Module:
    model = RnnAutoencoder()
    model.load_state_dict(state_dict, strict=True)
    return model


def _load_gru(state_dict: dict[str, Any]) -> nn.Module:
    model = GruAutoencoder()
    model.load_state_dict(state_dict, strict=True)
    return model


_LOADERS = {
    "artifact-lstm-ae-v3": _load_lstm,
    "artifact-conv1d-v3": _load_conv1d,
    "artifact-transformer-v3": _load_transformer,
    "artifact-rnn-v3": _load_rnn,
    "artifact-gru-v3": _load_gru,
}


def build_model(version: str, state_dict: dict[str, Any]) -> nn.Module:
    loader = _LOADERS.get(version)
    if loader is None:
        raise ValueError(f"no artifact architecture registered for {version!r}")
    return loader(state_dict)
