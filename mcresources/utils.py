#  Part of mcresources by Alex O'Neill
#  Work under copyright. Licensed under MIT
#  For more information see the project LICENSE file

from collections import namedtuple
from json import dump as json_dump
from os import makedirs, listdir, remove as rmf, rmdir
from os.path import join as path_join, dirname, isfile
from typing import Union, Sequence, Any, Dict, List, Callable, Tuple


ResourceLocation = namedtuple('ResourceLocation', ('domain', 'path'))
ResourceIdentifier = Union[ResourceLocation, Sequence[str], str]
Json = Union[Dict[str, Any], Sequence[Any], str]


def clean_generated_resources(path: str = 'src/main/resources'):
    """
    Recursively removes all files generated using by mcresources, as identified by the inserted comment.
    Removes empty directories
    :param path: the initial path to search through
    """
    for subdir in listdir(path):
        sub_path = path_join(path, subdir)
        if isfile(sub_path):
            # File, check if valid and then delete
            if subdir.endswith('.json'):
                delete = False
                with open(sub_path, 'r') as file:
                    if '"__comment__": "This file was automatically created by mcresources"' in file.read():
                        delete = True
                if delete:
                    rmf(sub_path)
        else:
            # Folder, search recursively
            clean_generated_resources(sub_path)

        if not listdir(path):
            # Delete empty folder
            rmdir(path)


def del_none(data_in: Json) -> Json:
    # Removes all "None" entries in a dictionary, list or tuple, recursively
    if isinstance(data_in, Dict):
        return dict((key, del_none(value)) for key, value in data_in.items() if value is not None)
    elif is_sequence(data_in):
        return [del_none(p) for p in data_in if p is not None]
    elif data_in is not None:
        return data_in
    else:
        raise ValueError('None passed to `del_none`, should not be possible.')


def write(path_parts: Sequence[str], data: Json, indent: int = 2):
    # write output to json
    path = path_join(*path_parts) + '.json'
    makedirs(dirname(path), exist_ok=True)
    data = del_none({'__comment__': 'This file was automatically created by mcresources', **data})
    with open(path, 'w') as file:
        json_dump(data, file, indent=indent)


def resource_location(*elements: ResourceIdentifier) -> ResourceLocation:
    """
    Parses a ResourceLocation from a series of elements. Can accept:
    - A ResourceLocation, return it
    - A Sequence[str], representing a '/' joined resource path.
    - A 'domain:path' representing a domain specification
    Then either a single element, or an optional domain followed by data element.
    If a domain is present in the data, the first optional domain is ignored.
    If no domain is present, the `minecraft` domain is inferred.
    """
    if len(elements) not in {1, 2}:
        raise RuntimeError('Must take one or two arguments: [optional] domain, and path elements')
    if len(elements) == 1:
        domain, data = 'minecraft', elements[0]
    else:
        domain, data = elements[0], elements[1]
    if isinstance(data, ResourceLocation):
        return data
    else:
        joined = '/'.join(str_path(data))
        if ':' in joined:
            i = joined.index(':')
            return ResourceLocation(joined[:i], joined[i + 1:])
        else:
            return ResourceLocation(domain, joined)


def simple_resource_location(data: ResourceIdentifier, use_minecraft_domain: bool = False) -> str:
    res = resource_location('minecraft', data)
    if res.domain == 'minecraft' and not use_minecraft_domain:
        return res.path
    else:
        return '%s:%s' % res


def str_path(data_in: Sequence[str]) -> List[str]:
    # Converts an iterable or string to a string list, but respects '/', for use in path construction
    if isinstance(data_in, str):
        return [s for s in data_in.split('/')]
    elif isinstance(data_in, Sequence):
        return [*flatten_list([str_path(s) for s in data_in])]
    else:
        raise RuntimeError('Unknown object %s at str_path' % str(data_in))


def str_list(data_in: Sequence[str]) -> List[str]:
    # Converts an iterable or string to a string list
    if isinstance(data_in, str):
        return [data_in]
    elif isinstance(data_in, Sequence):
        return [*flatten_list(data_in)]
    else:
        raise RuntimeError('Unknown object %s at str_list' % str(data_in))


def domain_path_parts(name_parts: Sequence[str], default_domain: str) -> Tuple[str, List[str]]:
    joined = '/'.join(str_path(name_parts))
    if ':' in joined:
        i = joined.index(':')
        return joined[:i], joined[i + 1:].split('/')
    else:
        return default_domain, str_path(joined)


def flatten_list(container: Sequence[Any]) -> Sequence[Any]:
    # Turns nested lists of lists into a flat list of items
    # Use for part functions that need to be wrapped in a single list:
    # [*flatten_list([function_returns_list(p) for p in iterable])]
    for i in container:
        if is_sequence(i):
            for j in flatten_list(i):
                yield j
        else:
            yield i


def dict_get(data_in: Dict[Any, Any], key: Any, default: Any = None, map_function: Callable[[Any], Any] = None) -> Any:
    # Gets an element from a dictionary by key
    # If the element is not present, it returns the default value
    # If the element is present, and a map function is supplied, it will apply the map function to the object
    if key in data_in:
        if map_function is None:
            return data_in[key]
        else:
            return map_function(data_in[key])
    else:
        return default


def is_sequence(data_in: Any) -> bool:
    return isinstance(data_in, Sequence) and not isinstance(data_in, str)

# ================== ASSET PARTS ===================


def recipe_condition(data_in: Json, strict: bool = False) -> Union[List, None]:
    if data_in is None:
        return None
    elif isinstance(data_in, str):
        return [{'type': data_in}]
    elif isinstance(data_in, Dict):
        return [data_in]
    elif is_sequence(data_in) and not strict:
        return [*flatten_list([recipe_condition(c, True) for c in data_in])]
    else:
        raise RuntimeError('Unknown object %s at recipe_condition' % str(data_in))


def item_stack(data_in: Json) -> Dict[str, Any]:
    if isinstance(data_in, str):
        if data_in[0:4] == 'tag!':
            return {'tag': data_in[4:]}
        else:
            return {'item': data_in}
    elif isinstance(data_in, Dict):
        return data_in
    elif is_sequence(data_in):
        if len(data_in) != 2:
            raise RuntimeError('An item stack as a sequence must have two entries (size, item)')
        return {
            'count': data_in[0],
            **item_stack(data_in[1])
        }
    else:
        raise RuntimeError('Unknown object %s at item_stack' % str(data_in))


def item_stack_list(data_in: Json) -> List[Dict[str, Any]]:
    if isinstance(data_in, str) or isinstance(data_in, Dict):
        return [item_stack(data_in)]
    elif isinstance(data_in, Sequence):
        return [*flatten_list([item_stack(s) for s in data_in])]
    else:
        raise RuntimeError('Unknown object %s at item_stack_list' % str(data_in))


def item_stack_dict(data_in: Union[Dict[str, Any], str], default_char: str = '#') -> dict:
    if isinstance(data_in, Dict):
        return dict((k, item_stack(v)) for k, v in data_in.items())
    elif isinstance(data_in, str):
        return {default_char: item_stack(data_in)}
    else:
        raise RuntimeError('Unknown object %s at item_stack_dict' % str(data_in))


def item_model_textures(data_in: Json) -> Dict[str, Any]:
    if isinstance(data_in, str):
        return {'layer0': data_in}
    elif isinstance(data_in, Sequence):
        return dict(('layer%d' % i, data_in[i]) for i in range(len(data_in)))
    elif isinstance(data_in, Dict):
        return data_in
    else:
        raise RuntimeError('Unknown object %s at item_model_textures' % str(data_in))


def blockstate_multipart_parts(data_in: Sequence[Json]) -> List[Dict[str, Any]]:
    def part(p: Union[Sequence[Json], Json]) -> Dict[str, Any]:
        if isinstance(p, Sequence) and len(p) == 2:
            return {'when': p[0], 'apply': p[1]}
        elif isinstance(p, Dict):
            return {'apply': p}
        else:
            raise RuntimeError('Unknown object %s at blockstate_multipart_parts#part' % str(p))

    return [part(p) for p in data_in]


def lang_parts(data_in: Sequence[Json], entries: Dict[str, str] = None) -> Dict[str, str]:
    if entries is None:
        entries = {}
    i = 0
    while i < len(data_in):
        part = data_in[i]
        if isinstance(part, str):
            value = data_in[i + 1]
            entries[part] = value
            i += 1
        elif isinstance(part, Sequence):
            lang_parts(part, entries)
        elif isinstance(part, Dict):
            entries.update(part)
        else:
            raise RuntimeError('Unknown object %s at lang_parts' % str(part))
        i += 1
    return entries


# ================== LOOT TABLES ===================


def loot_pool_list(data_in: Json, loot_type: str) -> List[Dict[str, Any]]:
    # Top level loot pool parser
    if isinstance(data_in, str):
        # Simplest loot pool, construct a single entry
        return [{
            'name': 'loot_pool',
            'rolls': 1,
            'entries': loot_entry_list(data_in),
            'conditions': loot_default_conditions(loot_type),
        }]
    elif isinstance(data_in, Dict):
        # Single loot pool with any amount of things specified
        return [{
            'name': 'loot_pool',
            'rolls': dict_get(data_in, 'rolls', 1),
            'bonus_rolls': dict_get(data_in, 'bonus_rolls'),
            'entries': dict_get(data_in, 'entries', data_in, map_function=loot_entry_list),
            'conditions': dict_get(data_in, 'conditions', default=loot_default_conditions(loot_type),
                                   map_function=loot_condition_list),
            'functions': dict_get(data_in, 'functions', map_function=loot_function_list),
        }]
    elif isinstance(data_in, Sequence):
        # List of pools, so flatten the list and try make a loot pool list for each entry
        return [*flatten_list([loot_pool_list(p, loot_type) for p in data_in])]
    else:
        raise RuntimeError('Unknown object %s at loot_pool_list' % str(data_in))


def loot_entry_list(data_in: Json) -> List[Dict[str, Any]]:
    # Creates a single loot pool entry
    if isinstance(data_in, str):
        # String, so either create an item or a tag based drop
        if data_in[0:4] == 'tag!':
            return [{'type': 'minecraft:tag', 'name': data_in[4:]}]
        else:
            return [{'type': 'minecraft:item', 'name': data_in}]
    elif isinstance(data_in, Sequence):
        # iterable, so create a loot entry list for each element and flatten
        return [*flatten_list([loot_entry_list(p) for p in data_in])]
    elif isinstance(data_in, Dict):
        # dict, so check through available parameters and construct a loot entry from those
        return [{
            'type': dict_get(data_in, 'type', default='item'),
            'conditions': dict_get(data_in, 'conditions', map_function=loot_condition_list),
            'name': dict_get(data_in, 'name'),
            'children': dict_get(data_in, 'children'),
            'expand': dict_get(data_in, 'expand'),
            'functions': dict_get(data_in, 'functions', map_function=loot_function_list),
            'weight': dict_get(data_in, 'weight'),
            'quality': dict_get(data_in, 'quality')
        }]
    else:
        raise RuntimeError('Unknown object %s at loot_entry_list' % str(data_in))


def loot_function_list(data_in: Json) -> List[Dict[str, Any]]:
    # a list of loot pool functions
    if isinstance(data_in, str):
        # string, so just accept a name
        return [{'function': data_in}]
    elif isinstance(data_in, Sequence):
        # iterable, so create a list for each condition and flatten
        return [*flatten_list([loot_function_list(p) for p in data_in])]
    elif isinstance(data_in, Dict):
        # dict, so just use raw data
        return [data_in]
    else:
        raise RuntimeError('Unknown object %s at loot_function_list' % str(data_in))


def loot_condition_list(data_in: Json) -> List[Dict[str, Any]]:
    # a list of loot pool conditions
    if isinstance(data_in, str):
        # string, so just accept a name
        return [{'condition': data_in}]
    elif isinstance(data_in, Sequence):
        # iterable, so create a list for each condition and flatten
        return [*flatten_list([loot_condition_list(p) for p in data_in])]
    elif isinstance(data_in, Dict):
        # dict, so just use raw data
        return [data_in]
    else:
        raise RuntimeError('Unknown object %s at loot_condition_list' % str(data_in))


def loot_default_conditions(loot_type: str) -> Union[List[Dict[str, Any]], None]:
    if loot_type == 'block':
        return [{'condition': 'minecraft:survives_explosion'}]
    else:
        return None


# ================== STANDARD BLOCKSTATES ===================


def slab_variants(block: str, block_slab: str, block_slab_top: str):
    return {
        'type=bottom': {'model': block_slab},
        'type=top': {'model': block_slab_top},
        'type=double': {'model': block}
    }


def stairs_variants(stairs: str, stairs_inner: str, stairs_outer: str) -> Dict[str, Any]:
    return {
        'facing=east,half=bottom,shape=straight': {'model': stairs},
        'facing=west,half=bottom,shape=straight': {'model': stairs, 'y': 180, 'uvlock': True},
        'facing=south,half=bottom,shape=straight': {'model': stairs, 'y': 90, 'uvlock': True},
        'facing=north,half=bottom,shape=straight': {'model': stairs, 'y': 270, 'uvlock': True},
        'facing=east,half=bottom,shape=outer_right': {'model': stairs_outer},
        'facing=west,half=bottom,shape=outer_right': {'model': stairs_outer, 'y': 180, 'uvlock': True},
        'facing=south,half=bottom,shape=outer_right': {'model': stairs_outer, 'y': 90, 'uvlock': True},
        'facing=north,half=bottom,shape=outer_right': {'model': stairs_outer, 'y': 270, 'uvlock': True},
        'facing=east,half=bottom,shape=outer_left': {'model': stairs_outer, 'y': 270, 'uvlock': True},
        'facing=west,half=bottom,shape=outer_left': {'model': stairs_outer, 'y': 90, 'uvlock': True},
        'facing=south,half=bottom,shape=outer_left': {'model': stairs_outer},
        'facing=north,half=bottom,shape=outer_left': {'model': stairs_outer, 'y': 180, 'uvlock': True},
        'facing=east,half=bottom,shape=inner_right': {'model': stairs_inner},
        'facing=west,half=bottom,shape=inner_right': {'model': stairs_inner, 'y': 180, 'uvlock': True},
        'facing=south,half=bottom,shape=inner_right': {'model': stairs_inner, 'y': 90, 'uvlock': True},
        'facing=north,half=bottom,shape=inner_right': {'model': stairs_inner, 'y': 270, 'uvlock': True},
        'facing=east,half=bottom,shape=inner_left': {'model': stairs_inner, 'y': 270, 'uvlock': True},
        'facing=west,half=bottom,shape=inner_left': {'model': stairs_inner, 'y': 90, 'uvlock': True},
        'facing=south,half=bottom,shape=inner_left': {'model': stairs_inner},
        'facing=north,half=bottom,shape=inner_left': {'model': stairs_inner, 'y': 180, 'uvlock': True},
        'facing=east,half=top,shape=straight': {'model': stairs, 'x': 180, 'uvlock': True},
        'facing=west,half=top,shape=straight': {'model': stairs, 'x': 180, 'y': 180, 'uvlock': True},
        'facing=south,half=top,shape=straight': {'model': stairs, 'x': 180, 'y': 90, 'uvlock': True},
        'facing=north,half=top,shape=straight': {'model': stairs, 'x': 180, 'y': 270, 'uvlock': True},
        'facing=east,half=top,shape=outer_right': {'model': stairs_outer, 'x': 180, 'y': 90, 'uvlock': True},
        'facing=west,half=top,shape=outer_right': {'model': stairs_outer, 'x': 180, 'y': 270, 'uvlock': True},
        'facing=south,half=top,shape=outer_right': {'model': stairs_outer, 'x': 180, 'y': 180, 'uvlock': True},
        'facing=north,half=top,shape=outer_right': {'model': stairs_outer, 'x': 180, 'uvlock': True},
        'facing=east,half=top,shape=outer_left': {'model': stairs_outer, 'x': 180, 'uvlock': True},
        'facing=west,half=top,shape=outer_left': {'model': stairs_outer, 'x': 180, 'y': 180, 'uvlock': True},
        'facing=south,half=top,shape=outer_left': {'model': stairs_outer, 'x': 180, 'y': 90, 'uvlock': True},
        'facing=north,half=top,shape=outer_left': {'model': stairs_outer, 'x': 180, 'y': 270, 'uvlock': True},
        'facing=east,half=top,shape=inner_right': {'model': stairs_inner, 'x': 180, 'y': 90, 'uvlock': True},
        'facing=west,half=top,shape=inner_right': {'model': stairs_inner, 'x': 180, 'y': 270, 'uvlock': True},
        'facing=south,half=top,shape=inner_right': {'model': stairs_inner, 'x': 180, 'y': 180, 'uvlock': True},
        'facing=north,half=top,shape=inner_right': {'model': stairs_inner, 'x': 180, 'uvlock': True},
        'facing=east,half=top,shape=inner_left': {'model': stairs_inner, 'x': 180, 'uvlock': True},
        'facing=west,half=top,shape=inner_left': {'model': stairs_inner, 'x': 180, 'y': 180, 'uvlock': True},
        'facing=south,half=top,shape=inner_left': {'model': stairs_inner, 'x': 180, 'y': 90, 'uvlock': True},
        'facing=north,half=top,shape=inner_left': {'model': stairs_inner, 'x': 180, 'y': 270, 'uvlock': True}
    }


def fence_multipart(fence_post: str, fence_side) -> List[Any]:
    return [
        {'model': fence_post},
        ({'north': 'true'}, {'model': fence_side, 'uvlock': True}),
        ({'east': 'true'}, {'model': fence_side, 'y': 90, 'uvlock': True}),
        ({'south': 'true'}, {'model': fence_side, 'y': 180, 'uvlock': True}),
        ({'west': 'true'}, {'model': fence_side, 'y': 270, 'uvlock': True})
    ]


def fence_gate_variants(fence_gate: str, fence_gate_open: str, fence_gate_wall: str, fence_gate_wall_open: str) -> Dict[str, Any]:
    return {
        'facing=south,in_wall=false,open=false': {'model': fence_gate, 'uvlock': True},
        'facing=west,in_wall=false,open=false': {'model': fence_gate, 'uvlock': True, 'y': 90},
        'facing=north,in_wall=false,open=false': {'model': fence_gate, 'uvlock': True, 'y': 180},
        'facing=east,in_wall=false,open=false': {'model': fence_gate, 'uvlock': True, 'y': 270},
        'facing=south,in_wall=false,open=true': {'model': fence_gate_open, 'uvlock': True},
        'facing=west,in_wall=false,open=true': {'model': fence_gate_open, 'uvlock': True, 'y': 90},
        'facing=north,in_wall=false,open=true': {'model': fence_gate_open, 'uvlock': True, 'y': 180},
        'facing=east,in_wall=false,open=true': {'model': fence_gate_open, 'uvlock': True, 'y': 270},
        'facing=south,in_wall=true,open=false': {'model': fence_gate_wall, 'uvlock': True},
        'facing=west,in_wall=true,open=false': {'model': fence_gate_wall, 'uvlock': True, 'y': 90},
        'facing=north,in_wall=true,open=false': {'model': fence_gate_wall, 'uvlock': True, 'y': 180},
        'facing=east,in_wall=true,open=false': {'model': fence_gate_wall, 'uvlock': True, 'y': 270},
        'facing=south,in_wall=true,open=true': {'model': fence_gate_wall_open, 'uvlock': True},
        'facing=west,in_wall=true,open=true': {'model': fence_gate_wall_open, 'uvlock': True, 'y': 90},
        'facing=north,in_wall=true,open=true': {'model': fence_gate_wall_open, 'uvlock': True, 'y': 180},
        'facing=east,in_wall=true,open=true': {'model': fence_gate_wall_open, 'uvlock': True, 'y': 270}
    }


def wall_multipart(wall_post: str, wall_side: str) -> List[Any]:
    return [
        ({'up': 'true'}, {'model': wall_post}),
        ({'north': 'true'}, {'model': wall_side, 'uvlock': True}),
        ({'east': 'true'}, {'model': wall_side, 'y': 90, 'uvlock': True}),
        ({'south': 'true'}, {'model': wall_side, 'y': 180, 'uvlock': True}),
        ({'west': 'true'}, {'model': wall_side, 'y': 270, 'uvlock': True})
    ]
