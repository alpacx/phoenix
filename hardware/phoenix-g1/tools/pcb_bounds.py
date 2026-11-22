"""Bounding-box helpers for the KiCad SWIG Python bindings."""

def inflated_box(item, margin):
    # Inflate returns a borrowed reference. Keep the owning value through return.
    bounds = item.GetBoundingBox()
    bounds.Inflate(margin)
    return bounds


def point_distance_squared(bounds, point):
    """Exact point-to-rectangle distance in integer board units."""
    dx = max(bounds.GetLeft()-point.x, point.x-bounds.GetRight(), 0)
    dy = max(bounds.GetTop()-point.y, point.y-bounds.GetBottom(), 0)
    return dx*dx + dy*dy
