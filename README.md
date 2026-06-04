# python-getpaid-simulator

Payment gateway simulator host for testing the python-getpaid ecosystem.

The simulator no longer owns provider implementations directly. It starts a
generic Litestar host, discovers provider plugins from installed packages, and
mounts each provider's API routes and UI flows through entry points.

## Installation

```bash
pip install python-getpaid-simulator
```

The host only becomes useful when at least one provider package exposing the
simulator plugin entry point is installed in the same environment.

## Plugin Model

Provider packages must expose an entry point in the
`getpaid.simulator.providers` group.

Example from a provider package:

```toml
[project.entry-points."getpaid.simulator.providers"]
payu = "getpaid_payu.simulator:get_plugin"
```

The entry point must resolve to a factory returning a
`getpaid_simulator.spi.SimulatorProviderPlugin`.

The current stable plugin contract requires:

- `api_version`
- `slug`
- `display_name`
- `api_handlers`
- `ui_handlers`
- `transitions`
- `load_config(env)`
- optional `authorize_path_template`

The host validates the plugin slug against the entry point name and rejects
plugins that do not match `getpaid_simulator.spi.SIMULATOR_PLUGIN_API_VERSION`.

## Startup Failure Modes

Plugin loading is controlled by `SIMULATOR_PLUGIN_FAILURE_MODE` or the CLI flag
`--plugin-failure-mode`.

- `warn` (default): broken plugins are skipped, the simulator starts in
  degraded mode, and failed providers appear in logs, `/`, `/sim/status`, and
  the dashboard.
- `strict`: the first plugin import, factory, compatibility, or config failure
  aborts startup with `PluginLoadError`.

Examples:

```bash
getpaid-simulator --plugin-failure-mode strict
SIMULATOR_PLUGIN_FAILURE_MODE=warn getpaid-simulator
```

## Provider Packaging

Provider packages should keep simulator support in an optional dependency group
such as `simulator`, rather than forcing simulator host and Litestar
dependencies into normal runtime installs.

Example:

```toml
[project.optional-dependencies]
simulator = [
    "python-getpaid-simulator>=3.0.0",
    "litestar>=2.0",
]
```

## Development Notes

- Wave 1 storage remains in-memory behind the host storage interface.
- Provider-local simulator code lives in provider repositories, not under
  `getpaid_simulator.providers`.

## License

MIT
