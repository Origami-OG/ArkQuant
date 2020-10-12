# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 12 15:37:47 2019

@author: python
"""
from collections import OrderedDict
import numpy as np, pandas as pd

_MINUTE_TO_SESSION_OHCLV_HOW = OrderedDict((
    ('open', 'first'),
    ('high', 'max'),
    ('low', 'min'),
    ('close', 'last'),
    ('volume', 'sum'),
))


def minute_frame_to_session_frame(minute_frame, calendar):

    """
    Resample a DataFrame with minute data into the frame expected by a
    BcolzDailyBarWriter.

    Parameters
    ----------
    minute_frame : pd.DataFrame
        A DataFrame with the columns `open`, `high`, `low`, `close`, `volume`,
        and `dt` (minute dts)
    calendar : trading_calendars.trading_calendar.TradingCalendar
        A TradingCalendar on which session labels to resample from minute
        to session.

    Return
    ------
    session_frame : pd.DataFrame
        A DataFrame with the columns `open`, `high`, `low`, `close`, `volume`,
        and `day` (datetime-like).
    """
    how = OrderedDict((c, _MINUTE_TO_SESSION_OHCLV_HOW[c])
                      for c in minute_frame.columns)
    # index --- session lable : ticker
    labels = calendar.minute_index_to_session_labels(minute_frame.index)
    # how --- field : func(string)
    return minute_frame.groupby(labels).agg(how)


class DailyHistoryAggregator(object):
    """
    Converts minute pricing data into a daily summary, to be used for the
    last slot in a call to history with a frequency of `1d`.

    This summary is the same as a daily bar rollup of minute data, with the
    distinction that the summary is truncated to the `dt` requested.
    i.e. the aggregation slides forward during a the course of nakedquant day.

    Provides aggregation for `open`, `high`, `low`, `close`, and `volume`.
    The aggregation rules for each price type is documented in their respective

    """

    def __init__(self, market_opens, minute_reader, trading_calendar):
        self._market_opens = market_opens
        self._minute_reader = minute_reader
        self._trading_calendar = trading_calendar

        # The caches are structured as (date, market_open, entries), where
        # entries is a dict of asset -> (last_visited_dt, value)
        #
        # Whenever an aggregation method determines the current value,
        # the entry for the respective asset should be overwritten with a new
        # entry for the current dt.value (int) and aggregation value.
        #
        # When the requested dt's date is different from date the cache is
        # flushed, so that the cache entries do not grow unbounded.
        #
        # Example cache:
        # cache = (date(2016, 3, 17),
        #          pd.Timestamp('2016-03-17 13:31', tz='UTC'),
        #          {
        #              1: (1458221460000000000, np.nan),
        #              2: (1458221460000000000, 42.0),
        #         })
        self._caches = {
            'open': None,
            'high': None,
            'low': None,
            'close': None,
            'volume': None
        }

        # The int value is used for deltas to avoid extra computation from
        # creating new Timestamps.
        self._one_min = pd.Timedelta('1 min').value

    def _prelude(self, dt, field):
        session = self._trading_calendar.minute_to_session_label(dt)
        dt_value = dt.value
        cache = self._caches[field]
        if cache is None or cache[0] != session:
            market_open = self._market_opens.loc[session]
            cache = self._caches[field] = (session, market_open, {})

        _, market_open, entries = cache
        market_open = market_open.tz_localize('UTC')
        if dt != market_open:
            prev_dt = dt_value - self._one_min
        else:
            prev_dt = None
        return market_open, prev_dt, dt_value, entries

    def opens(self, assets, dt):
        """
        The open field's aggregation returns the first value that occurs
        for the day, if there has been no data on or before the `dt` the open
        is `nan`.

        Once the first non-nan open is seen, that value remains constant per
        asset for the remainder of the day.

        Returns
        -------
        np.array with dtype=float64, in order of asset parameter.
        """
        market_open, prev_dt, dt_value, entries = self._prelude(dt, 'open')

        opens = []
        session_label = self._trading_calendar.minute_to_session_label(dt)

        for asset in assets:
            if not asset.is_alive_for_session(session_label):
                opens.append(np.NaN)
                continue

            if prev_dt is None:
                val = self._minute_reader.get_value(asset, dt, 'open')
                entries[asset] = (dt_value, val)
                opens.append(val)
                continue
            else:
                try:
                    last_visited_dt, first_open = entries[asset]
                    if last_visited_dt == dt_value:
                        opens.append(first_open)
                        continue
                    elif not pd.isnull(first_open):
                        opens.append(first_open)
                        entries[asset] = (dt_value, first_open)
                        continue
                    else:
                        after_last = pd.Timestamp(
                            last_visited_dt + self._one_min, tz='UTC')
                        window = self._minute_reader.load_raw_arrays(
                            ['open'],
                            after_last,
                            dt,
                            [asset],
                        )[0]
                        nonnan = window[~pd.isnull(window)]
                        if len(nonnan):
                            val = nonnan[0]
                        else:
                            val = np.nan
                        entries[asset] = (dt_value, val)
                        opens.append(val)
                        continue
                except KeyError:
                    window = self._minute_reader.load_raw_arrays(
                        ['open'],
                        market_open,
                        dt,
                        [asset],
                    )[0]
                    nonnan = window[~pd.isnull(window)]
                    if len(nonnan):
                        val = nonnan[0]
                    else:
                        val = np.nan
                    entries[asset] = (dt_value, val)
                    opens.append(val)
                    continue
        return np.array(opens)

    def highs(self, assets, dt):
        """
        The high field's aggregation returns the largest high seen between
        the market open and the current dt.
        If there has been no data on or before the `dt` the high is `nan`.

        Returns
        -------
        np.array with dtype=float64, in order of asset parameter.
        """
        market_open, prev_dt, dt_value, entries = self._prelude(dt, 'high')

        highs = []
        session_label = self._trading_calendar.minute_to_session_label(dt)

        for asset in assets:
            if not asset.is_alive_for_session(session_label):
                highs.append(np.NaN)
                continue

            if prev_dt is None:
                val = self._minute_reader.get_value(asset, dt, 'high')
                entries[asset] = (dt_value, val)
                highs.append(val)
                continue
            else:
                try:
                    last_visited_dt, last_max = entries[asset]
                    if last_visited_dt == dt_value:
                        highs.append(last_max)
                        continue
                    elif last_visited_dt == prev_dt:
                        curr_val = self._minute_reader.get_value(
                            asset, dt, 'high')
                        if pd.isnull(curr_val):
                            val = last_max
                        elif pd.isnull(last_max):
                            val = curr_val
                        else:
                            val = max(last_max, curr_val)
                        entries[asset] = (dt_value, val)
                        highs.append(val)
                        continue
                    else:
                        after_last = pd.Timestamp(
                            last_visited_dt + self._one_min, tz='UTC')
                        window = self._minute_reader.load_raw_arrays(
                            ['high'],
                            after_last,
                            dt,
                            [asset],
                        )[0].T
                        val = np.nanmax(np.append(window, last_max))
                        entries[asset] = (dt_value, val)
                        highs.append(val)
                        continue
                except KeyError:
                    window = self._minute_reader.load_raw_arrays(
                        ['high'],
                        market_open,
                        dt,
                        [asset],
                    )[0].T
                    val = np.nanmax(window)
                    entries[asset] = (dt_value, val)
                    highs.append(val)
                    continue
        return np.array(highs)

    def lows(self, assets, dt):
        """
        The low field's aggregation returns the smallest low seen between
        the market open and the current dt.
        If there has been no data on or before the `dt` the low is `nan`.

        Returns
        -------
        np.array with dtype=float64, in order of asset parameter.
        """
        market_open, prev_dt, dt_value, entries = self._prelude(dt, 'low')

        lows = []
        session_label = self._trading_calendar.minute_to_session_label(dt)

        for asset in assets:
            if not asset.is_alive_for_session(session_label):
                lows.append(np.NaN)
                continue

            if prev_dt is None:
                val = self._minute_reader.get_value(asset, dt, 'low')
                entries[asset] = (dt_value, val)
                lows.append(val)
                continue
            else:
                try:
                    last_visited_dt, last_min = entries[asset]
                    if last_visited_dt == dt_value:
                        lows.append(last_min)
                        continue
                    elif last_visited_dt == prev_dt:
                        curr_val = self._minute_reader.get_value(
                            asset, dt, 'low')
                        val = np.nanmin([last_min, curr_val])
                        entries[asset] = (dt_value, val)
                        lows.append(val)
                        continue
                    else:
                        after_last = pd.Timestamp(
                            last_visited_dt + self._one_min, tz='UTC')
                        window = self._minute_reader.load_raw_arrays(
                            ['low'],
                            after_last,
                            dt,
                            [asset],
                        )[0].T
                        val = np.nanmin(np.append(window, last_min))
                        entries[asset] = (dt_value, val)
                        lows.append(val)
                        continue
                except KeyError:
                    window = self._minute_reader.load_raw_arrays(
                        ['low'],
                        market_open,
                        dt,
                        [asset],
                    )[0].T
                    val = np.nanmin(window)
                    entries[asset] = (dt_value, val)
                    lows.append(val)
                    continue
        return np.array(lows)

    def closes(self, assets, dt):
        """
        The close field's aggregation returns the latest close at the given
        dt.
        If the close for the given dt is `nan`, the most recent non-nan
        `close` is used.
        If there has been no data on or before the `dt` the close is `nan`.

        Returns
        -------
        np.array with dtype=float64, in order of asset parameter.
        """
        market_open, prev_dt, dt_value, entries = self._prelude(dt, 'close')

        closes = []
        session_label = self._trading_calendar.minute_to_session_label(dt)

        def _get_filled_close(asset):
            """
            Returns the most recent non-nan close for the asset in this
            session. If there has been no data in this session on or before the
            `dt`, returns `nan`
            """
            window = self._minute_reader.load_raw_arrays(
                ['close'],
                market_open,
                dt,
                [asset],
            )[0]
            try:
                return window[~np.isnan(window)][-1]
            except IndexError:
                return np.NaN

        for asset in assets:
            if not asset.is_alive_for_session(session_label):
                closes.append(np.NaN)
                continue

            if prev_dt is None:
                val = self._minute_reader.get_value(asset, dt, 'close')
                entries[asset] = (dt_value, val)
                closes.append(val)
                continue
            else:
                try:
                    last_visited_dt, last_close = entries[asset]
                    if last_visited_dt == dt_value:
                        closes.append(last_close)
                        continue
                    elif last_visited_dt == prev_dt:
                        val = self._minute_reader.get_value(
                            asset, dt, 'close')
                        if pd.isnull(val):
                            val = last_close
                        entries[asset] = (dt_value, val)
                        closes.append(val)
                        continue
                    else:
                        val = self._minute_reader.get_value(
                            asset, dt, 'close')
                        if pd.isnull(val):
                            val = _get_filled_close(asset)
                        entries[asset] = (dt_value, val)
                        closes.append(val)
                        continue
                except KeyError:
                    val = self._minute_reader.get_value(
                        asset, dt, 'close')
                    if pd.isnull(val):
                        val = _get_filled_close(asset)
                    entries[asset] = (dt_value, val)
                    closes.append(val)
                    continue
        return np.array(closes)

    def volumes(self, assets, dt):
        """
        The volume field's aggregation returns the sum of all volumes
        between the market open and the `dt`
        If there has been no data on or before the `dt` the volume is 0.

        Returns
        -------
        np.array with dtype=int64, in order of asset parameter.
        """
        market_open, prev_dt, dt_value, entries = self._prelude(dt, 'volume')

        volumes = []
        session_label = self._trading_calendar.minute_to_session_label(dt)

        for asset in assets:
            if not asset.is_alive_for_session(session_label):
                volumes.append(0)
                continue

            if prev_dt is None:
                val = self._minute_reader.get_value(asset, dt, 'volume')
                entries[asset] = (dt_value, val)
                volumes.append(val)
                continue
            else:
                try:
                    last_visited_dt, last_total = entries[asset]
                    if last_visited_dt == dt_value:
                        volumes.append(last_total)
                        continue
                    elif last_visited_dt == prev_dt:
                        val = self._minute_reader.get_value(
                            asset, dt, 'volume')
                        val += last_total
                        entries[asset] = (dt_value, val)
                        volumes.append(val)
                        continue
                    else:
                        after_last = pd.Timestamp(
                            last_visited_dt + self._one_min, tz='UTC')
                        window = self._minute_reader.load_raw_arrays(
                            ['volume'],
                            after_last,
                            dt,
                            [asset],
                        )[0]
                        val = np.nansum(window) + last_total
                        entries[asset] = (dt_value, val)
                        volumes.append(val)
                        continue
                except KeyError:
                    window = self._minute_reader.load_raw_arrays(
                        ['volume'],
                        market_open,
                        dt,
                        [asset],
                    )[0]
                    val = np.nansum(window)
                    entries[asset] = (dt_value, val)
                    volumes.append(val)
                    continue
        return np.array(volumes)
