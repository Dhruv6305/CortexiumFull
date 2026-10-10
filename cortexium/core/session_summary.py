import time
from collections import Counter

class SessionSummary:
    def __init__(self):
        self.start_time = time.time()
        self.scores = []
        self.violations = []
        
    def update(self, score, suggestions):
        self.scores.append(score)
        if suggestions:
            self.violations.extend(suggestions)
            
    def print_summary(self):
        duration = time.time() - self.start_time
        avg_score = sum(self.scores) / len(self.scores) if self.scores else 0
        
        print("\n" + "="*40)
        print(" 🧠 CORTEXIUM - Session Summary")
        print("="*40)
        print(f" ⏱ Duration:       {duration:.1f} seconds")
        print(f" 🎯 Average Score:  {avg_score:.1f}/100")
        print(f" ⚠ Violations:     {len(self.violations)} recorded incidents")
        if self.violations:
            print("\n Breakdown:")
            counts = Counter(self.violations)
            for k, v in counts.items():
                print(f"    - {k}: {v} times")
        print("="*40 + "\n")
