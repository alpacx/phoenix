"""Only the two PHY crystal pad necks may use 0.15 mm width; clearance unchanged."""
PHY_CLOCK_NECK_RULE='\n(rule "PHY crystal pin neck" (condition "A.Type == \'Track\' && (A.NetName == \'PHY_XIN\' || A.NetName == \'PHY_XOUT\') && A.intersectsCourtyard(\'U5\')") (constraint track_width (min 0.15mm)))\n'
