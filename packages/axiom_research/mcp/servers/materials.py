from axiom_research.mcp.runner import port_from_env, run_server

NAME = "axiom-research-mcp-materials"
INSTRUCTIONS = (
    "Computed material properties (Materials Project) and compound metadata (PubChem). "
    "Metadata only. Never label computed properties as experimental."
)


def main() -> None:
    run_server(name=NAME, instructions=INSTRUCTIONS, port=port_from_env())


if __name__ == "__main__":
    main()
