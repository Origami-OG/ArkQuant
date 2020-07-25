"""
Base class for Pipeline API data loaders.
"""
from abc import ABC,abstractmethod


class PipelineLoader(ABC):
    """Interface for PipelineLoaders.
    """
    def _resolve_domains(self,domains,event_type = False):
        pipeline_domain = self._preprocess_domains(domains)
        if event_type and self._validate_event(pipeline_domain):
            return pipeline_domain
        return pipeline_domain

    def _preprocess_domains(self, domains):
        """
        Domain has _fields and specify trading_calendar for computing term
        Verify domains and attempt to compose domains to a composite domain
        where intergrated fields and date_tuples.

        The default implementation is a no-op.
        """
        pipeline_domain = domains[0].copy()
        for domain in domains[1:]:
            pipeline_domain = pipeline_domain | domain
        return pipeline_domain

    @classmethod
    def _validate_event(cls,domain):
        """
        Verify that the columns of ``events`` can be used by an EventsLoader to
        serve the BoundColumns described by ``next_value_columns`` and
        ``previous_value_columns``.
        """
        event_type = domain.domain_field
        missing = set(event_type) - cls.EVENT_OP_NAME
        if missing:
            raise ValueError(
                "EventsLoader missing required columns {missing}.\n"
                "Got Columns: {received}\n"
                "Expected Columns: {required}".format(
                    missing=sorted(missing),
                    received=sorted(event_type),
                    required=sorted(cls.EVENT_OP_NAME),
                )
            )
        return True

    @abstractmethod
    def load_pipeline_arrays(self, dt,sids):
        """
        Load data for ``columns`` as AdjustedArrays.

        Parameters
        ----------
        dates : pd.DatetimeIndex
            Dates for which data is being requested.
        sids : pd.Int64Index
            Asset identifiers for which data is being requested.

        Returns
        -------
        arrays : dict[BoundColumn -> zipline.lib.adjusted_array.AdjustedArray]
            Map from column to an AdjustedArray representing a point-in-time
            rolling view over the requested dates for the requested sids.
        """
        raise NotImplementedError