"""Test the timetable generation and verify output."""
import json
import sys
sys.stdout.reconfigure(line_buffering=True)

from scheduler.utils.loader import load_all_data
from scheduler.algorithms.class_timetable_csp import ClassTimetableCSP
from scheduler.algorithms.lab_timetable_csp import LabTimetableCSP

print("Loading data...", flush=True)
r, s, e, t, c, ts = load_all_data()

print("Generating class timetable...", flush=True)
ct = ClassTimetableCSP(r, t, c, ts, s).solve()

print("Generating lab timetable...", flush=True)
lt = LabTimetableCSP(r, t, c, ts, s, ct).solve()

print(f"\n=== RESULTS ===", flush=True)
print(f"Total class assignments: {len(ct)}", flush=True)
print(f"Total lab assignments: {len(lt)}", flush=True)

# Check CS semester 5 section A
cs5a_classes = [k for k in ct.keys() if 'CSBS05' in k and '|A|' in k]
cs5a_labs = [k for k in lt.keys() if 'CSBS05' in k and '|A' in k]
print(f"\nCS Semester 5 Section A:", flush=True)
print(f"  Theory classes: {len(cs5a_classes)}", flush=True)
for c_key in sorted(cs5a_classes):
    val = ct[c_key]
    print(f"    {c_key}: {val.get('slot')} in {val.get('room')}", flush=True)
print(f"  Labs: {len(cs5a_labs)}", flush=True)
for l_key in sorted(cs5a_labs):
    val = lt[l_key]
    print(f"    {l_key}: {val.get('slots')} in {val.get('room')}", flush=True)

# Check CS semester 7 section A
cs7a_classes = [k for k in ct.keys() if 'CSBS07' in k and '|A|' in k]
cs7a_labs = [k for k in lt.keys() if 'CSBS07' in k and '|A' in k]
print(f"\nCS Semester 7 Section A:", flush=True)
print(f"  Theory classes: {len(cs7a_classes)}", flush=True)
print(f"  Labs: {len(cs7a_labs)}", flush=True)

# Save to cache
print("\nSaving timetable cache...", flush=True)
cache = {
    'class_timetable': ct, 
    'lab_timetable': lt, 
    'rooms': r, 
    'teachers': t, 
    'courses': c, 
    'timeslots': ts
}
with open('../uploads/generated_timetable.json', 'w') as f:
    json.dump(cache, f)
print("Done!", flush=True)
