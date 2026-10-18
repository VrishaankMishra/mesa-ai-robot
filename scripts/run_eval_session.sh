#!/usr/bin/env bash
# One domain-shift evaluation session with the standard medication set and probe.
#
#     scripts/run_eval_session.sh <room> <condition> [extra eval_capture.py args]
#     scripts/run_eval_session.sh living_room midday_lamps_off
#
# <room> is the site label (lowercase snake_case, chosen once per room). <condition> must
# be one of the eight grid labels so a typo cannot create a ninth cell.
set -euo pipefail
cd "$(dirname "$0")/.."

room=${1:?usage: $0 <room> <condition>}
cond=${2:?usage: $0 <room> <condition>}
shift 2

conditions="morning_lamps_off morning_lamps_on midday_lamps_off midday_lamp_added
evening_lights_on evening_lamp_added evening_dim evening_dim_lamp"
case " $conditions " in
  *" $cond "*) ;;
  *) echo "unknown condition '$cond'. One of:"; printf '  %s\n' $conditions; exit 2 ;;
esac
if [[ ! "$room" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "room label must be lowercase snake_case (got '$room')"; exit 2
fi

exec .venv/bin/python -u scripts/eval_capture.py \
    --site "$room" --condition "$cond" \
    --bottles mylanta,vitamin_d3,bayer_aspirin,cvs_allergy,omeprazole,melatonin,ashwagandha,advil \
    --unknown benadryl "$@"
