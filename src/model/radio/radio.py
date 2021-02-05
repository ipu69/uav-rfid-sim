import numpy as np
from scipy import special


def dbm2w(value_dbm: float):
    return 10 ** (value_dbm / 10 - 3)


def w2dbm(value_watt: float):
    return 10 * np.log10(value_watt) + 30 if value_watt >= 1e-15 else -np.inf


def db2lin(value_db: float):
    return 10 ** (value_db / 10)


def lin2db(value_linear: float):
    return 10 * np.log10(value_linear) if value_linear >= 1e-15 else -np.inf


def signal2noise(rx_power: float, noise_power: float):
    """
    Computes Signal-to-Noise ratio. Input parameters are in logarithmic scale.
    :param rx_power:
    :param noise_power:
    :return:
    """
    return db2lin(rx_power - noise_power)


def ber_over_awgn(snr):
    """
    Computes BER in an additive white gaussian noise (AWGN) channel for
    Binary Phase Shift Keying (BPSK)
    :param snr: the extended SNR
    :return:
    """

    # noinspection PyUnresolvedReferences
    def q_function(x):
        return 0.5 - 0.5 * special.erf(x / 2 ** 0.5)

    t = q_function(snr ** 0.5)
    return 2 * t * (1 - t)


def dipole_rp(azimuth):
    """
    Returns dipole directional gain
    :param azimuth:
    :return:
    """
    c = np.cos(azimuth)
    s = np.sin(azimuth)
    if c > 1e-9:
        return np.abs(np.cos(np.pi / 2 * s) / c)
    else:
        return 0.0


# def free_space_path_loss_2d(*, distance, tx_rp, rx_rp, tx_angle, rx_angle, tx_height, rx_height, wavelen, **kwargs):
#     """
#     Computes free space signal attenuation between the transmitter and the receiver in linear scale.
#     :param distance: the distance between transmitter and receiver
#     :param rx_angle: a mount angle of transmitter antenna
#     :param tx_angle: a mount angle of receiver antenna
#     :param tx_rp: a radiation pattern of the transmitter
#     :param rx_rp: a radiation pattern of the receiver
#     :param tx_height: a mount height of the transmitter
#     :param rx_height: a mount height of the receiver
#     :param wavelen: a wavelen of signal carrier
#     :return: free space path loss in linear scale
#     """
#     # Ray geometry computation
#     delta_height = np.abs(tx_height - rx_height)
#     d0 = (delta_height ** 2 + distance ** 2) ** 0.5
#     alpha0 = np.arctan(distance / delta_height)
#
#     # Attenuation caused by radiation pattern
#     g0 = (tx_rp(azimuth=alpha0 - tx_angle, tilt=np.pi/2, wavelen=wavelen, **kwargs) *
#           rx_rp(azimuth=alpha0 - rx_angle, tilt=np.pi/2, wavelen=wavelen, **kwargs))
#
#     k = wavelen / (4 * np.pi)
#     return (k * g0 / d0) ** 2

def free_space_path_loss(distance, height, wavelen, rp_tx=dipole_rp, rp_rx=dipole_rp):
    """
    Computes free space signal attenuation between the transmitter and the
    receiver in linear scale.
    :param distance: the distance between transmitter and receiver
    :param height: UAV height
    :param wavelen: a wavelen of signal carrier
    :param rp_tx: sender radiation pattern
    :param rp_rx: receiver radiation pattern
    :return: free space path loss in linear scale
    """
    alpha = np.arccos(height / distance)
    g = rp_tx(alpha) * rp_rx(alpha)
    return g * (wavelen / (4 * np.pi * distance)) ** 2


def sync_angle(snr, preamble_duration=9.3e-6, bandwidth=1.2e6, **kwargs):
    """
    Computes the angle of de-synchronisation.
    :param snr: an SNR of the received signal
    :param preamble_duration: the duration of PHY-preamble in seconds
    :param bandwidth: the bandwidth of the signal in herzs
    :param kwargs:
    :return: the angle of de-synchronisation
    """
    return (snr * preamble_duration * bandwidth) ** -0.5


# noinspection PyUnusedLocal
def snr_extended(snr, sync_phi=0, miller=1, symbol_duration=1.25e-6, bandwidth=1.2e6, **kwargs):
    """
    Computes the extended SNR for BER computation.
    :param snr: an SNR of the received signal
    :param sync_phi: the de-synchronization
    :param miller: the order of Miller encoding
    :param symbol_duration: the symbol duration in seconds
    :param bandwidth: the bandwidth of the signal in herzs
    :param kwargs:
    :return: the extended SNR for BER computation
    """
    return miller * snr * symbol_duration * bandwidth * np.cos(sync_phi) ** 2
