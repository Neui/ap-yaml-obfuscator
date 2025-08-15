Obfuscate Archipelago YAMLs
===========================

You need to have [`PyYAML`](https://pypi.org/project/PyYAML/) installed:
```sh
python3 -m pip install -r requirements.txt
```

## `obfuscate.py`

The `obfuscate.py` rewrites the YAML file to use the unicode character syntax for every string, and removes all whitespace where possible.

```
$ python3 obfuscate.py -h
usage: obfuscate.py [-h] input output

Obfuscate YAML

positional arguments:
  input       Input YAML
  output      Output obfuscated YAML

options:
  -h, --help  show this help message and exit
```

## `ap-obfuscate.py`

The `ap-obfuscate.py` tries to add indirect triggers to better hide the actual options used.
Note that this doesn't work with every YAML because it assumes almost every option is about assigning weights rather than something like `starting_inventory`.
Only some options are hardcoded to be ignored. Plando isn't supported.

```
$ python3 ap-obfuscate.py -h
usage: ap-obfuscate.py [-h] input output

Obfuscate YAML

positional arguments:
  input       Input AP YAML
  output      Output obfuscated AP YAML

options:
  -h, --help  show this help message and exit
```
