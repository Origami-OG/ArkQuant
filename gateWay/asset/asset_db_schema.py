# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 12 15:37:47 2019

@author: python
"""
import sqlalchemy as sa
from gateWay.driver.db_schema import engine
# Define a version number for the database generated by these writers
# Increment this version number any time a change is made to the schema of the
# asset database
# NOTE: When upgrading this remember to add a downgrade in:
# .asset_db_migrations
ASSET_DB_VERSION = 7

# A frozenset of the names of all tables in the asset db
# NOTE: When modifying this schema, update the ASSET_DB_VERSION value
asset_db_table_names = frozenset([
                            'asset_router',
                            'equity_basics',
                            'convertible_basics',
                            'version_info',
                                ])

metadata = sa.MetaData(bind=engine)

asset_router = sa.Table(
    'asset_router',
    metadata,
    sa.Column(
        'id',
        sa.Integer,
        autoincrement=True
    ),
    sa.Column(
        'sid',
        sa.Integer,
        unique=True,
        nullable=False,
        primary_key=True,
        index=True
    ),
    # asset_name --- 公司名称
    sa.Column(
        'asset_name',
        # sa.String(6),
        sa.Text,
        unique=True,
        nullable=False
    ),
    sa.Column(
        'asset_type',
        sa.String(10),
        nullable=False
    ),
    sa.Column(
        'exchange',
        sa.String(6)
    ),
    sa.Column(
        'first_traded',
        sa.String(16),
        # nullable=False
    ),
    sa.Column(
        'last_traded',
        sa.String(10),
        default='null'
    ),
    # null / d / p / st  --- null(normal)
    sa.Column(
        'status',
        sa.String(6),
        default='null'
    ),
    sa.Column(
        'country_code',
        sa.String(6),
        default='ch'
    ),

)

equity_basics = sa.Table(
    'equity_basics',
    metadata,
    sa.Column(
        'sid',
        sa.Integer,
        sa.ForeignKey(asset_router.c.sid),
        index=True,
        nullable=False,
        primary_key=True
    ),
    sa.Table(
        'dual',
        sa.String(8),
        default='null'
    ),
    sa.Column(
        'broker',
        sa.Text,
        nullable=False
    ),
    # district code
    sa.Column(
        'district',
        sa.String(8),
        nullable=False
    ),
    sa.Column(
        'initial_price',
        sa.Numeric(10, 2),
        nullable=False
    ),
    sa.Column(
        'business_scope',
        sa.Text,
        nullable=False
    ),
)

convertible_basics = sa.Table(
    'convertible_basics',
    metadata,
    sa.Column(
        'sid',
        sa.Integer,
        sa.ForeignKey(asset_router.c.sid),
        unique=True,
        nullable=False,
        primary_key=True,
        index=True
    ),
    sa.Column(
        # 股票可以发行不止一个可转债
        'swap_code',
        sa.String(6),
        nullable=False,
        primary_key=True
    ),
    sa.Column(
        'put_price',
        sa.Numeric(10, 3),
        nullable=False
    ),
    sa.Column(
        'redeem_price',
        sa.Numeric(10, 2),
        nullable=False
    ),
    sa.Column(
        'convert_price',
        sa.Numeric(10, 2),
        nullable=False
    ),
    sa.Column(
        'convert_dt',
        sa.String(10),
        nullable=False
    ),
    sa.Column(
        'put_convert_price',
        sa.Numeric(10, 2),
        nullable=False
    ),
    sa.Column(
        'guarantor',
        sa.Text,
        nullable=False
    ),
)


version_info = sa.Table(
    'version_info',
    metadata,
    sa.Column(
        'id',
        sa.Integer,
        unique=True,
        nullable=False,
        primary_key=True,
    ),
    sa.Column(
        'version',
        sa.Integer,
        unique=True,
        nullable=False,
    ),
    # This constraint ensures a single entry in this table
    sa.CheckConstraint('id <= 1'),
)