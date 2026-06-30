"""Entry point: ``python3 -m nectar.diagnostics`` runs the environment doctor."""

import sys

from nectar.diagnostics.doctor import main

sys.exit(main())
