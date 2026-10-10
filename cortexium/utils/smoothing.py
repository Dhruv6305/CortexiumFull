class Smoother:
    def __init__(self, alpha=0.5):
        self.alpha = alpha
        self.prev = None
        
    def smooth(self, current):
        if self.prev is None:
            self.prev = current
            return current
            
        if isinstance(current, (int, float)):
            smoothed = self.alpha * self.prev + (1 - self.alpha) * current
        elif isinstance(current, tuple):
            smoothed = tuple(self.alpha * p + (1 - self.alpha) * c for p, c in zip(self.prev, current))
        elif isinstance(current, list):
            smoothed = [self.alpha * p + (1 - self.alpha) * c for p, c in zip(self.prev, current)]
        else:
            smoothed = current
            
        self.prev = smoothed
        return smoothed
