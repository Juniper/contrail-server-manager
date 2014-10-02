import abc


class DeviceEnvBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_pwr_consumption(self):
        """Retrieve power consumption in watts from the target nodes and return the value."""
        raise NotImplementedError('subclasses must override get_pwr_consumption()!')
