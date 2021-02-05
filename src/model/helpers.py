from typing import Any, Iterable, Tuple

import model.objects

DEFAULT_PARAMS = {
    'scene.max_distance': 15.0,
    'scene.position_update_interval': 0.1,
    'scene.max_num_rounds': -1,
    'scene.verbose': False,

    'reader.position': (0, 0, 10.0),
    'reader.speed': (1.0, 0, 0),
    'reader.Q': 2,
    'reader.M': "M2",
    'reader.sel': "All",
    'reader.trext': False,
    'reader.dr': '64/3',
    'reader.tari': 6.25e-6,
    'reader.rtcal': 15.0e-6,
    'reader.trcal': 20.0e-6,
    'reader.session': 'S0',
    'reader.target': 'A',
    'reader.wordcnt': 4,
    'reader.tx_power': 31.5,  # dBm
    'reader.circulator_noise': -80.0,  # dBm

    'tag.position': (0, 0, 0),
    'tag.sensitivity': -18.0,  # dBm
    'tag.epcid_wordcnt': 6,
    'tag.modulation_loss': -10.0,  # dBm,

    'channel_type': model.objects.ConstChannelSpec,
    'channel.thermal_noise': model.objects.channel.THERMAL_NOISE,
    'channel.speed_of_light': model.objects.channel.SPEED_OF_LIGHT,
    # 'channel.connection_distance': 11.0,
    # 'channel.path_loss': -40.0,
    # 'channel.ber': 0.01,
}


def subdict(d: dict, prefix: str) -> dict:
    dot_prefix = f'{prefix}.'
    l = len(dot_prefix)
    return {
        k[l:]: v
        for k, v in d.items() if k.startswith(dot_prefix)
    }


def dict2spec(d: dict):
    channel_type = d.get('channel_type', model.objects.ConstChannelSpec)

    reader_spec = model.objects.ReaderSpec(**subdict(d, 'reader'))
    tag_spec = model.objects.TagSpec(**subdict(d, 'tag'))
    channel_spec = channel_type(**subdict(d, 'channel'))
    scene_spec = model.objects.SceneSpec(
        reader=reader_spec,
        tag=tag_spec,
        channel=channel_spec,
        **subdict(d, 'scene')
    )

    return scene_spec


def update_dict(d: dict, kws) -> dict:
    new_d = {k: v for k, v in d.items()}
    for k, v in kws.items():
        new_d[k] = v
    return new_d


def spawn_dict(d: dict, key: str, values_list: Iterable) -> Tuple[dict]:
    return tuple(update_dict(d, {key: v}) for v in values_list)
