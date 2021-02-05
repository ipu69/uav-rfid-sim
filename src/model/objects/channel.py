from dataclasses import dataclass, field

import numpy as np

from model.objects.reader import Reader
from model.objects.tag import Tag
from model.radio.radio import dbm2w, w2dbm, signal2noise, free_space_path_loss, \
    ber_over_awgn, db2lin, lin2db

THERMAL_NOISE = -110  # dBm
SPEED_OF_LIGHT = 299792458


@dataclass
class ChannelSpec:
    thermal_noise: float = THERMAL_NOISE
    speed_of_light: float = SPEED_OF_LIGHT


@dataclass
class ConstChannelSpec(ChannelSpec):
    connection_distance: float = 11.0
    ber: float = 0.01
    path_loss: float = -40.0  # dBm


@dataclass
class AWGNChannelSpec(ChannelSpec):
    frequency: float = 860e6


class TimeValueMap:
    def __init__(self, default: float = THERMAL_NOISE):
        self._time = []
        self._values = []
        self._default = default

    def record(self, time, power):
        self._time.append(time)
        self._values.append(power)

    @property
    def time(self):
        return self._time

    @property
    def values(self):
        return self._values

    def __len__(self):
        return len(self._time)

    def get(self, time):
        # Most of the time we will be interested in the latest values,
        # so instead of binary search, use linear search from the tail:
        for i in range(len(self._time) - 1, -1, -1):
            if self._time[i] <= time:
                return self._values[i]
        return self._default

    @property
    def last(self):
        return self._values[-1] if len(self._values) > 0 else self._default

    def get_min(self, t0: float, t1: float) -> float:
        assert t0 <= t1
        time, values = self._time, self._values

        if not bool(time):
            return self._default
        if t0 >= time[-1]:
            return values[-1]

        # Find i1: time[i1] > t1, but time[i1 - 1] <= t1
        i1 = 0
        for i in range(len(time) - 1, -1, -1):
            if time[i] <= t1:
                i1 = i + 1
                break

        # Find i0: time[i0] <= t0, but time[i0 + 1] > t0
        i0 = -1
        for i in range(i1 - 1, -1, -1):
            if time[i] <= t0:
                i0 = i
                break
        if i0 < 0:
            return self._default

        return min(values[i0:i1])

    def __str__(self):
        return ", ".join(str(x) for x in zip(self._time, self._values))


@dataclass
class Channel:
    thermal_noise: float = THERMAL_NOISE
    speed_of_light: float = SPEED_OF_LIGHT

    # Derived constants:
    thermal_noise_watt: float = field(init=False)

    # Mappings:
    tag_rx_power_map: TimeValueMap = field(init=False)
    tag_tx_power_map: TimeValueMap = field(init=False)
    reader_rx_power_map: TimeValueMap = field(init=False)
    distance_map: TimeValueMap = field(init=False)
    ber_map: TimeValueMap = field(init=False)
    snr_map: TimeValueMap = field(init=False)
    path_loss_map: TimeValueMap = field(init=False)
    dx_map: TimeValueMap = field(init=False)
    dy_map: TimeValueMap = field(init=False)
    dz_map: TimeValueMap = field(init=False)

    # Fields filled once after the first call (e.g., redaer noise):
    reader_noise_watt: float = field(init=False, default=0)
    reader_noise_dbm: float = field(init=False, default=-np.inf)

    def __post_init__(self):
        self.tag_rx_power_map = TimeValueMap(default=-np.inf)
        self.tag_tx_power_map = TimeValueMap(default=-np.inf)
        self.reader_rx_power_map = TimeValueMap(default=-np.inf)
        self.distance_map = TimeValueMap()
        self.ber_map = TimeValueMap(default=1.0)
        self.snr_map = TimeValueMap(default=0.0)
        self.path_loss_map = TimeValueMap(default=-np.inf)
        self.dx_map = TimeValueMap(default=np.inf)
        self.dy_map = TimeValueMap(default=np.inf)
        self.dz_map = TimeValueMap(default=np.inf)

        self.thermal_noise_watt = dbm2w(self.thermal_noise)

        self.reader_noise_watt = -1

    def get_propagation_delay(self, reader_pos, tag_pos):
        return np.linalg.norm(reader_pos - tag_pos) / self.speed_of_light

    def _get_path_loss(self, d):
        raise NotImplementedError

    def _get_ber(self, snr):
        raise NotImplementedError

    def update_power(self, time: float, reader: Reader, tag: Tag):
        pr, pt = reader.position, tag.position
        d = np.linalg.norm(pr - pt)
        self.distance_map.record(time, d)
        self.dx_map.record(time, pr[0] - pt[0])
        self.dy_map.record(time, pr[1] - pt[1])
        self.dz_map.record(time, pr[2] - pt[2])

        pl = self._get_path_loss(d)
        tag_rx = reader.tx_power + pl
        tag_tx = tag_rx + tag.modulation_loss
        reader_rx = tag_tx + pl

        self.tag_tx_power_map.record(time, tag_tx)
        self.tag_rx_power_map.record(time, tag_rx)
        self.reader_rx_power_map.record(time, reader_rx)
        self.path_loss_map.record(time, pl)

        noise_watt = self.reader_noise_watt
        if noise_watt < 0:
            noise_watt = dbm2w(reader.circulator_noise) + \
                         dbm2w(self.thermal_noise)
            self.reader_noise_watt = noise_watt
            self.reader_noise_dbm = w2dbm(noise_watt)
        noise_dbm = self.reader_noise_dbm

        snr = signal2noise(reader_rx, noise_dbm)
        self.snr_map.record(time, snr)

        ber = self._get_ber(snr)
        self.ber_map.record(time, ber)

    def str_state(self):
        return f'\tdistance       : {self.distance_map.last:.2f} m\n' \
               f'\ttag rx power   : {self.tag_rx_power_map.last:.2f} dBm\n' \
               f'\ttag tx power   : {self.tag_tx_power_map.last:.2f} dBm\n' \
               f'\treader rx power: {self.reader_rx_power_map.last:.2f} dBm\n' \
               f'\treader SNR     : {self.snr_map.last:.2f}\n' \
               f'\treader BER     : {self.ber_map.last:.2f}'


@dataclass
class ConstChannel(Channel):
    connection_distance: float = 11.0
    path_loss: float = -40.0
    ber: float = 0.01
    noconn_path_loss: float = -200.0

    def _get_ber(self, snr):
        return 1.0 if snr < 0.5 else self.ber

    def _get_path_loss(self, d):
        return self.path_loss if d <= self.connection_distance else \
            self.noconn_path_loss


@dataclass
class AWGNChannel(Channel):
    frequency: float = 860e6

    def _get_ber(self, snr):
        return ber_over_awgn(snr)

    def _get_path_loss(self, d):
        wavelen = self.speed_of_light / self.frequency
        return lin2db(free_space_path_loss(d, wavelen))


def create_channel(spec):
    if isinstance(spec, ConstChannelSpec):
        return ConstChannel(
            thermal_noise=spec.thermal_noise,
            speed_of_light=spec.speed_of_light,
            connection_distance=spec.connection_distance,
            path_loss=spec.path_loss,
            ber=spec.ber,
        )
    elif isinstance(spec, AWGNChannelSpec):
        return AWGNChannel(
            thermal_noise=spec.thermal_noise,
            speed_of_light=spec.speed_of_light,
            frequency=spec.frequency
        )
    raise TypeError(f'unrecognized channel spec. type "{type(spec)}"')
