import argparse
from pathlib import Path

from talk_to_vibe.runtime_paths import InstallManifest, build_launch_agent_plist, load_install_manifest, write_install_manifest


def write_manifest(args: argparse.Namespace) -> int:
    manifest = InstallManifest(
        app_path=args.app_path,
        helper_path=args.helper_path,
        launch_agent_path=args.launch_agent_path,
        bundle_identifier=args.bundle_identifier,
        launch_at_login=args.launch_at_login,
        brew_packages=args.brew_package,
        install_version=args.install_version,
    )
    write_install_manifest(manifest, Path(args.path))
    return 0


def print_manifest_field(args: argparse.Namespace) -> int:
    manifest = load_install_manifest(Path(args.path))
    if manifest is None:
        return 1
    value = getattr(manifest, args.field)
    if isinstance(value, list):
        print("\n".join(value))
    else:
        print(value)
    return 0


def write_launch_agent(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_launch_agent_plist(Path(args.app_path)), encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TalkToVibe macOS install helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("write-manifest")
    manifest_parser.add_argument("--path", required=True)
    manifest_parser.add_argument("--app-path", required=True)
    manifest_parser.add_argument("--helper-path", required=True)
    manifest_parser.add_argument("--launch-agent-path", required=True)
    manifest_parser.add_argument("--bundle-identifier", required=True)
    manifest_parser.add_argument("--launch-at-login", action="store_true")
    manifest_parser.add_argument("--brew-package", action="append", default=[])
    manifest_parser.add_argument("--install-version", required=True)
    manifest_parser.set_defaults(func=write_manifest)

    field_parser = subparsers.add_parser("print-manifest-field")
    field_parser.add_argument("--path", required=True)
    field_parser.add_argument("--field", required=True, choices=sorted(InstallManifest.__dataclass_fields__.keys()))
    field_parser.set_defaults(func=print_manifest_field)

    launch_agent_parser = subparsers.add_parser("write-launch-agent")
    launch_agent_parser.add_argument("--output", required=True)
    launch_agent_parser.add_argument("--app-path", required=True)
    launch_agent_parser.set_defaults(func=write_launch_agent)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
