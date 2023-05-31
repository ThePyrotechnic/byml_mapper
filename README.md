byml_mapper - Find relationships between actors in byml files
    Copyright (C) 2023  Michael Manis - michaelmanis@tutanota.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

## Setup

You will need to install this fork of the python [oead library](https://github.com/TotkMods/oead)

Cloning that repo and running 

- `git submodule update --init --recursive`
- `python setup.py install` 

should work.

You will need to dump your game and then unzip the ".zs" files. Use [ZStdTool](https://github.com/TotkMods/Totk.ZStdTool)

You can point this tool to a partial dump for faster searches

## Examples

First, read the help:

`python byml_mapper/byml_mapper.py -h`

Then, generate the cache:

`python byml_mapper/byml_mapper.py generate ./dump`

Search for a gyaml type:

`python byml_mapper/byml_mapper.py byaml Miasma_Sphere_5`

```json
[
    ...
    {
        "hash": 9712907587167295012,
        "gyaml": "Miasma_Sphere_5",
        "source": "wip/Banc/MainField/E-5_Static.bcett.byml",
        "files": [
        "wip/Banc/MainField/E-5_Static.bcett.byml"
        ]
    },
    ...
]

```

The `files` key will list each file where the object is listed somewhere else as a reference. In this case, the object is defined in `E-5_Static.bcett.byml`, but also referenced somewhere in the same file.

Search for a specific object:

`python byml_mapper/byml_mapper.py hash 9712907587167295012`

```json
[
  {
    "hash": 9712907587167295012,
    "gyaml": "Miasma_Sphere_5",
    "source": "wip/Banc/MainField/E-5_Static.bcett.byml",
    "files": [
      "wip/Banc/MainField/E-5_Static.bcett.byml"
    ]
  }
]
```

Update the cache (if you add / update / remove dumped files):

`python byml_mapper/byml_mapper.py generate ./dump`

Update the cache and run a search afterwards:

`python byml_mapper/byml_mapper.py hash 9712907587167295012 --update-cache ./dump`

To completely regenerate the cache, delete the `.cached_results` file

Or, run any command with the `--regenerate-cache` flag set to your dump path

`python byml_mapper/byml_mapper.py hash 9712907587167295012 --regenerate-cache ./dump`
