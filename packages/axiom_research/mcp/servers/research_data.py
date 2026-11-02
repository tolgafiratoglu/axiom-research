from axiom_research.mcp.runner import port_from_env, run_server

NAME = "axiom-research-mcp-research-data"
INSTRUCTIONS = (
    "Deposited research records (Zenodo) and independent PID resolve (DataCite). "
    "Metadata only: no bulk file harvest, no vector index."
)


def main() -> None:
    run_server(name=NAME, instructions=INSTRUCTIONS, port=port_from_env())


if __name__ == "__main__":
    main()
