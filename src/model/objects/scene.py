from dataclasses import field, dataclass

from model.objects.channel import create_channel, ChannelSpec, ConstChannelSpec
from model.objects.reader import ReaderSpec, create_reader
from model.objects.tag import create_tag, TagSpec


@dataclass
class SceneSpec:
    reader: ReaderSpec = field(default_factory=lambda: ReaderSpec())
    tag: TagSpec = field(default_factory=lambda: TagSpec())
    channel: ChannelSpec = field(default_factory=lambda: ConstChannelSpec())
    max_distance: float = 15.0
    position_update_interval: float = 0.1
    max_num_rounds: int = -1
    verbose: int = True


class Scene:
    def __init__(self, spec: SceneSpec):
        self.reader = create_reader(spec.reader)
        self.tag = create_tag(spec.tag, reader_spec=spec.reader)
        self.channel = create_channel(spec.channel)

        self.max_distance = spec.max_distance
        self.position_update_interval = spec.position_update_interval
        self.max_num_rounds = spec.max_num_rounds
        self.verbose = spec.verbose


def create_scene(spec: SceneSpec) -> Scene:
    return Scene(spec)
