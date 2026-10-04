// Coordinates are in CSS pixels relative to the layout viewport.
export function composerPlacement({ shellTop, shellBottom, navigationHeight, viewportTop, viewportHeight, restingHeight, focused, scale = 1, keyboardWasOpen = false }) {
  const keyboardOpen = Math.abs(scale - 1) < .05 && (focused || keyboardWasOpen) && restingHeight - viewportHeight > 100;
  return {
    keyboardOpen,
    bottom: keyboardOpen ? Math.max(8, shellBottom - viewportTop - viewportHeight + 8) : navigationHeight,
    top: Math.max(0, viewportTop - shellTop),
  };
}

export function compactInputHeight(textHeight, lineHeight, padding) {
  return Math.min(lineHeight * 3.5 + padding, Math.max(lineHeight + padding, textHeight));
}
