"""Corner anchors for the interface pieces that were laid out for a 4:3 screen (the laff meter, the Shticker Book button).
Their coordinates, and the tutorial script's, are written for that screen: a node placed with them under one of these anchors lands
where it always did on 4:3 but follows the real screen corner on any other shape, so on a phone or a narrow window it stays in view."""

_anchors = {}


def _anchor(name, corner, x, z=1.0):
    node = _anchors.get(name)
    if node is None or node.isEmpty():
        node = corner.attachNewNode(name)
        node.setPos(x, 0, z)
        _anchors[name] = node
    return node


def bottomRight():
    """Origin where aspect2d's (4/3, 0, -1) is on a 4:3 screen: the bottom right corner."""
    return _anchor('bottomRightAnchor', base.a2dBottomRight, -4.0 / 3.0)


def bottomLeft():
    """Origin where aspect2d's (-4/3, 0, -1) is on a 4:3 screen: the bottom left corner."""
    return _anchor('bottomLeftAnchor', base.a2dBottomLeft, 4.0 / 3.0)


def topLeft():
    """Origin where aspect2d's (-4/3, 0, 1) is on a 4:3 screen: the top left corner."""
    return _anchor('topLeftAnchor', base.a2dTopLeft, 4.0 / 3.0, -1.0)


def topLeftPopup():
    """The same corner in the popup layer (aspect2dp), which chat windows and menus live in."""
    return _anchor('topLeftPopupAnchor', base.a2dpTopLeft, 4.0 / 3.0, -1.0)
