#!/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'Author'
__email__ = 'Email'


# dependency
# built-in
import os
from functools import partial
# public
from torch.utils import data as torch_data
from transformers import AutoTokenizer
import lightning.pytorch as pl
from pytorch_lightning.loggers import WandbLogger
from lightning.pytorch.callbacks import ModelCheckpoint
from lightning.pytorch.callbacks.early_stopping import EarlyStopping
# private
from src.utils import helper
from src.models.nli import LitNLIClassifier
from src.datasets.qqp import Dataset as QQPDataset


class LitTrainer(object):
    """docstring for LitTrainer"""
    def __init__(self, config, **kwargs):
        super(LitTrainer, self).__init__()
        self.config = config
        self.update_config(**kwargs)
        self.initialize()
        self.setup_dataloader()

    def update_config(self, **kwargs):
        # update configuration accordingly
        for k,v in kwargs.items():
            setattr(self.config, k, v)

    def initialize(self):
        # model
        self.model = LitNLIClassifier(self.config)
        # tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.LM_PATH)
        # enable tokenizer multi-processing
        if self.config.num_workers > 0:
            os.environ["TOKENIZERS_PARALLELISM"] = "true"
        # callbacks
        early_stop_callback = EarlyStopping(
            monitor='val_acc'
            , min_delta=.0
            , patience=self.config.patience
            , verbose=True
            , mode='max'
            )
        checkpoint_callback = ModelCheckpoint(
            monitor='val_acc'
            , mode='max'
            )
        # logger
        self.logger = helper.init_logger(self.config)
        self.logger.info('Logger initialized.')
        self.wandb_logger = WandbLogger(
            name=self.config.NAME
            , save_dir=self.config.LOG_PATH
            , offline=self.config.OFFLINE
            , project=self.config.PROJECT
            , log_model='all'
            , entity=self.config.ENTITY
            )
        # trainer
        self.trainer = pl.Trainer(
            logger = self.wandb_logger
            , callbacks=[early_stop_callback, checkpoint_callback]
            , max_epochs=self.config.max_epochs
            , enable_checkpointing=True
            , enable_progress_bar=True
            , inference_mode=True
            )


    def setup_dataloader(self):
        train_dataset = QQPDataset('train', self.tokenizer, self.config)
        self.train_dataloader = torch_data.DataLoader(
            train_dataset
            , batch_size=self.config.train_batch_size
            , collate_fn=partial(train_dataset.collate_fn, self.tokenizer, True, self.config)
            , shuffle=True
            , num_workers=self.config.num_workers
            , pin_memory=True
            , drop_last=True
            )
        val_dataset = QQPDataset('val', self.tokenizer, self.config)
        self.val_dataloader = torch_data.DataLoader(
            val_dataset
            , batch_size=self.config.train_batch_size
            , collate_fn=partial(val_dataset.collate_fn, self.tokenizer, False, self.config)
            , shuffle=False
            , num_workers=self.config.num_workers
            , pin_memory=True
            , drop_last=False
            )

    def train(self):
        self.trainer.fit(
            model=self.model
            , train_dataloaders=self.train_dataloader
            , val_dataloaders=self.val_dataloader
            , ckpt_path=self.config.CKPT_PATH if self.config.load_ckpt else None
            )