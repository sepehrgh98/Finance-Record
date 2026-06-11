import json

from services.analyze_service import AnalyzeService


def main():
    report = AnalyzeService().analyze_directory("data/shoebox")

    print(
        json.dumps(
            report,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
