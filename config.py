from dynaconf import Dynaconf

settings = Dynaconf(
    settings_files=['settings.yaml'],
    environments=True,
    load_dotenv=True,
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load this files in the order.
