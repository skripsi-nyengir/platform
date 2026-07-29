"""Vendored trained-model architectures for artifact inference.

Reconstructions are copied verbatim from the validated offline harness so the
in-platform forward pass reproduces each checkpoint's stored reconstruction
within 1e-3 (Gate A). Do not "clean up" the forward math: parity is the contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

import torch
from torch import nn

WINDOW = 30


@dataclass(frozen=True)
class LstmAutoencoderConfig:
    input_channels: int
    hidden_size: int = 32
    latent_size: int = 16
    num_layers: int = 2
    dropout: float = 0.1
    bottleneck_mode: str = "channel"


class LstmAutoencoder(nn.Module):
    def __init__(self, config: LstmAutoencoderConfig) -> None:
        super().__init__()
        self.config = config
        c = config.input_channels
        h = config.hidden_size
        z = config.latent_size
        nl = config.num_layers
        self.encoder = nn.LSTM(
            input_size=c,
            hidden_size=h,
            num_layers=nl,
            batch_first=True,
            dropout=config.dropout if nl > 1 else 0.0,
        )
        self.to_latent = nn.Linear(h, z)
        self.decoder = nn.LSTM(
            input_size=z,
            hidden_size=h,
            num_layers=nl,
            batch_first=True,
            dropout=config.dropout if nl > 1 else 0.0,
        )
        self.to_output = nn.Linear(h, c)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        seq_len = inputs.shape[1]
        _, (h_n, _) = self.encoder(inputs)
        context = self.to_latent(h_n[-1])
        repeated = context.unsqueeze(1).expand(-1, seq_len, -1)
        out, _ = self.decoder(repeated)
        return cast(torch.Tensor, self.to_output(out))


class Conv1dAutoencoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv1d(2, 16, 3, stride=1, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 32, 3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv1d(32, 16, 3, stride=2, padding=1),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose1d(16, 32, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.ConvTranspose1d(32, 16, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 2, 3, padding=1),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        padded = torch.nn.functional.pad(values.transpose(1, 2), (0, 2))
        return self.decoder(self.encoder(padded)).transpose(1, 2)[:, :WINDOW]


class TransformerAutoencoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.position_embedding = nn.Parameter(torch.empty(1, WINDOW, 32))
        self.input_projection = nn.Linear(2, 32)
        self.transformer = nn.Transformer(
            d_model=32,
            nhead=4,
            num_encoder_layers=2,
            num_decoder_layers=2,
            dim_feedforward=64,
            dropout=0.1,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.output_projection = nn.Linear(32, 2)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        projected = self.input_projection(values)
        source = projected + self.position_embedding
        reconstructed = self.transformer(source, source)
        return cast(torch.Tensor, self.output_projection(reconstructed))


def _load_lstm(state_dict: dict[str, Any]) -> nn.Module:
    model = LstmAutoencoder(LstmAutoencoderConfig(input_channels=2))
    renamed = {
        key.replace("encoder.lstm.", "encoder.")
        .replace("encoder.to_latent.", "to_latent.")
        .replace("decoder.lstm.", "decoder.")
        .replace("decoder.to_output.", "to_output."): value
        for key, value in state_dict.items()
    }
    model.load_state_dict(renamed, strict=True)
    return model


def _load_conv1d(state_dict: dict[str, Any]) -> nn.Module:
    model = Conv1dAutoencoder()
    model.load_state_dict(state_dict, strict=True)
    return model


def _load_transformer(state_dict: dict[str, Any]) -> nn.Module:
    model = TransformerAutoencoder()
    model.load_state_dict(state_dict, strict=True)
    return model


_LOADERS = {
    "artifact-lstm-ae-v3": _load_lstm,
    "artifact-conv1d-v3": _load_conv1d,
    "artifact-transformer-v3": _load_transformer,
}


def build_model(version: str, state_dict: dict[str, Any]) -> nn.Module:
    loader = _LOADERS.get(version)
    if loader is None:
        raise ValueError(f"no artifact architecture registered for {version!r}")
    return loader(state_dict)
