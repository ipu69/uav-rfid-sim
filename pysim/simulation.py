from math import pi, cos, sin
from pprint import pprint

from pysim import events
from pysim.des import DES, Logger
from pysim.model import Network
from pysim.utils import random_hex_string


def initialize(sim):
    sim.schedule(events.UPDATE_POSITIONS)
    sim.schedule(events.START_ROUND)


def test_module():
    print('This is pysim.simulation module. '
          'If you see this, your PYTHONPATH is OK')


def simulate(spec, sim_time_limit=None, logger_level=Logger.Level.WARNING):
    print('started simulation, spec: ')
    pprint(spec)
    # sim_time_limit = 0.1
    ret = DES.simulate(Network, initialize=initialize, params=spec,
                       sim_time_limit=sim_time_limit,
                       logger_level=logger_level)
    # rounds = [ir for ir in ret.data.reader.rounds if ir['tags_on']]
    # for index, inventory_round in enumerate(rounds):
    #     print(index, ': ', inventory_round)

    return {
        'tags': [{
            'id': tag.id,
            'read_count': ret.data.reader.num_reads[tag.id]
        } for tag in ret.data.tags],
        'c1g2_stats': {'num_collisions': ret.data.reader.num_collisions},
        'read_timestamps': ret.data.reader.read_timestamps,
    }


if __name__ == '__main__':
    R = 10    # circle radius
    H = 1.0   # reader altitude
    V = 2.0   # meters per second, reader velocity
    D = 2.0   # meters, channel distance

    spec_ = {
        'mobility': {
            'update_timeout': 0.1,
        },
        'reader': {
            'position': (R, 0, H),
            'Q': 2,
            'M': 1,
            'DR': '8',
            'trext': False,
            'sel': 'ALL',
            'tari': 6.25e-6,
            'rtcal': 15.0e-6,
            'trcal': 20.0e-6,
            'session': 0,
            'target': 'A',
            'trajectory': {
                'center': (0, 0, 0),
                'radius': R,
                'velocity': V,  # meters per second
                'altitude': H,  # meter
            },
            'stats': {
                'record_read_timestamps': True,
            }
        },
        'tags': [{
            'id': i,
            'sensitivity': -20.0,  # dBm
            'position': (cos(pi/3 * i) * R, sin(pi/3 * i) * R, 0),
            'epcid': random_hex_string(24),
            'switch_target': False,
        } for i in range(6)],
        'channel': {
            'model': 'models.channels.ConstantChannel',
            'distance': D,
            'ber': 0.0,
        },
        'propagation': {
            'model': 'models.propagation.NoLossPropagationModel',
            'distance': D,
        },
    }

    # I define max simulation time as the time, needed to fly above each tag
    # twice, i.e. (2 - 1/12 - 0.0001) *pi*R / V. Subtracting 0.0001 is needed
    # to prohibit third attempt to connect to the first tag.
    sim_time_limit_ = (4 - 1/12 - 0.0001) * pi * R / V

    # Running the simulation:
    ret_ = simulate(spec_, sim_time_limit=sim_time_limit_)
    print(ret_)
