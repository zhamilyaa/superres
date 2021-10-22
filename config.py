# from dynaconf import Dynaconf
from box import Box
import os

settings = Box.from_yaml(filename='settings.yaml')[os.environ['ENV_FOR_DYNACONF']]
# settings = Dynaconf(
#     settings_files=['settings.yaml'],
#     environments=True,
#     load_dotenv=True,
# )

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load this files in the order.
