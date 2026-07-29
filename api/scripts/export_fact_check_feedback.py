import sys

from app.config import load_settings
from app.feedback_export import write_fact_check_feedback


def main() -> None:
    write_fact_check_feedback(load_settings().database_path, sys.stdout)


if __name__ == "__main__":
    main()
