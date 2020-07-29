# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 12 15:37:47 2019

@author: python
"""

import pandas as pd,warnings
from gateWay.assets.assets import Asset


def _deprecated_getitem_method(name, attrs):
    """Create a deprecated ``__getitem__`` method that tells users to use
    getattr instead.

    Parameters
    ----------
    name : str
        The name of the object in the warning message.
    attrs : iterable[str]
        The set of allowed attributes.

    Returns
    -------
    __getitem__ : callable[any, str]
        The ``__getitem__`` method to put in the class dict.
    """
    attrs = frozenset(attrs)
    msg = (
        "'{name}[{attr!r}]' is deprecated, please use"
        " '{name}.{attr}' instead"
    )

    def __getitem__(self, key):
        """``__getitem__`` is deprecated, please use attribute access instead.
        """
        warnings(msg.format(name=name, attr=key), DeprecationWarning, stacklevel=2)
        if key in attrs:
            return getattr(self, key)
        raise KeyError(key)

    return __getitem__


class InnerPosition:
    """The real values of a position.

    This exists to be owned by both a
    :class:`zipline.finance.position.Position` and a
    :class:`zipline.protocol.Position` at the same time without a cycle.
    """

    def __init__(self,
                 asset,
                 amount=0,
                 cost_basis=0.0,
                 last_sale_price=0.0,
                 last_sale_date=None):
        self.asset = asset
        self.amount = amount
        self.cost_basis = cost_basis  # per share
        self.last_sync_price = last_sale_price
        self.last_sync_date = last_sale_date

    def __repr__(self):
        return (
                '%s(asset=%r, amount=%r, cost_basis=%r,'
                ' last_sale_price=%r, last_sale_date=%r)' % (
                    type(self).__name__,
                    self.asset,
                    self.amount,
                    self.cost_basis,
                    self.last_sync_price,
                    self.last_sync_date,
                )
        )


class Position(object):
    """
    A protocol position

    Attributes
    ----------
    asset : zipline.assets.Asset
        The held asset.
    amount : int
        Number of shares held. Short positions are represented with negative
        values.
    cost_basis : float
        Average price at which currently-held shares were acquired.
    last_sale_price : float
        Most recent price for the position.
    last_sale_date : pd.Timestamp
        Datetime at which ``last_sale_price`` was last updated.
    """
    __slots__ = ('_underlying_position',)

    def __init__(self, underlying_position):
        object.__setattr__(self, '_underlying_position', underlying_position)

    def __getattr__(self, attr):
        return getattr(self._underlying_position, attr)

    def __setattr__(self, attr, value):
        raise AttributeError('cannot mutate Position objects')

    def __repr__(self):
        return 'Position(%r)' % {
            k: getattr(self, k)
            for k in (
                'asset',
                'amount',
                'cost_basis',
                'last_sale_price',
                'last_sale_date',
            )
        }

    # If you are adding new attributes, don't update this set. This method
    # is deprecated to normal attribute access so we don't want to encourage
    # new usages.
    __getitem__ = _deprecated_getitem_method(
        'position', {
            'sid',
            'amount',
            'cost_basis',
            'last_sale_price',
            'last_sale_date',
        },
    )


class Positions(dict):
    """A dict-like object containing the algorithm's current positions.
    """

    def __missing__(self, key):
        if isinstance(key, Asset):
            return Position(InnerPosition(key))
        else:
            raise TypeError("Position lookup expected a value of type Asset but got {0}"
                            " instead.".format(type(key).__name__))


class MutableView(object):
    """A mutable view over an "immutable" object.

    Parameters
    ----------
    ob : any
        The object to take a view over.
    """
    # add slots so we don't accidentally add attributes to the view instead of
    # ``ob``
    __slots__ = ('_mutable_view_obj')

    def __init__(self,ob):
        object.__setattr__(self,'_mutable_view_ob',ob)

    def __getattr__(self, item):
        return getattr(self._mutable_view_ob,item)

    def __setattr__(self,attr,value):
        #vars() 函数返回对象object的属性和属性值的字典对象 --- 扩展属性类型 ,不改变原来的对象属性
        vars(self._mutable_view_ob)[attr] = value

    def __repr__(self):
        return '%s(%r)'%(type(self).__name__,self._mutable_view_ob)


class Portfolio(object):
    """Object providing read-only access to current portfolio state.

    Parameters
    ----------
    start_date : pd.Timestamp
        The start date for the period being recorded.
    capital_base : float
        The starting value for the portfolio. This will be used as the starting
        cash, current cash, and portfolio value.

    Attributes
    ----------
    positions : zipline.protocol.Positions
        Dict-like object containing information about currently-held positions.
    cash : float
        Amount of cash currently held in portfolio.
    portfolio_value : float
        Current liquidation value of the portfolio's holdings.
        This is equal to ``cash + sum(shares * price)``
    starting_cash : float
        Amount of cash in the portfolio at the start of the backtest.
    """

    def __init__(self, capital_base=0.0):
        self_ = MutableView(self)
        self_.cash_flow = 0.0
        self_.starting_cash = capital_base
        self_.portfolio_value = capital_base
        self_.pnl = 0.0
        self_.returns = 0.0
        self_.cash = capital_base
        self_.positions = Positions()
        self_.positions_value = 0.0
        self_.positions_exposure = 0.0

    @property
    def capital_used(self):
        return self.cash_flow

    def __setattr__(self, attr, value):
        raise AttributeError('cannot mutate Portfolio objects')

    def __repr__(self):
        return "Portfolio({0})".format(self.__dict__)

    def __getattr__(self, item):
        return self.__dict__[item]

    # If you are adding new attributes, don't update this set. This method
    # is deprecated to normal attribute access so we don't want to encourage
    # new usages.
    __getitem__ = _deprecated_getitem_method(
        'portfolio', {
            'capital_used',
            'starting_cash',
            'portfolio_value',
            'pnl',
            'returns',
            'cash',
            'positions',
            'positions_value',
        },
    )

    @property
    def current_portfolio_weights(self):
        """
        Compute each asset's weight in the portfolio by calculating its held
        value divided by the total value of all positions.

        Each equity's value is its price times the number of shares held. Each
        futures contract's value is its unit price times number of shares held
        times the multiplier.
        """
        position_values = pd.Series({
            asset: (
                    position.last_sale_price *
                    position.amount *
                    asset.price_multiplier
            )
            for asset, position in self.positions.items()
        })
        return position_values / self.portfolio_value


class Account(object):
    """
    The account object tracks information about the trading account. The
    values are updated as the algorithm runs and its keys remain unchanged.
    If connected to a broker, one can update these values with the trading
    account values as reported by the broker.
    """

    def __init__(self):
        self_ = MutableView(self)
        self_.settled_cash = 0.0
        # 持仓
        self_.fund_positions_exposure = 0
        self_.equity_positions_exposure = 0
        self_.convertible_positions_exposure = 0
        self_.total_positions_exposure = 0
        # 持仓金额
        self_.equity_positions_value = 0.0
        self_.bond_positions_value = 0.0
        self_.fund_positions_value = 0.0
        self_.total_positions_value = 0.0
        self_.cushion = 0.0
        self_.net_leverage = 0.0

    def __repr__(self):
        return "Account({0})".format(self.__dict__)

    # If you are adding new attributes, don't update this set. This method
    # is deprecated to normal attribute access so we don't want to encourage
    # new usages.
    __getitem__ = _deprecated_getitem_method(
        'account', {
            'settled_cash',
            'fund_positions_exposure',
            'equity_positions_exposure',
            'convertible_positions_exposure',
            'total_positions_exposure',
            'fund_positions_value',
            'equity_positions_value',
            'convertible_positions_value',
            'total_positions_value',
            'cushion',
            'net_leverage',
        },
    )
