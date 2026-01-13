class BidirectionalArrow {
  constructor(svgId, cell1Id, cell2Id, labelText, style = 'solid', hoverText = '') {
    this.svg = document.getElementById(svgId);
    this.cell1 = document.getElementById(cell1Id);
    this.cell2 = document.getElementById(cell2Id);
    this.labelText = labelText;
    this.style = style; // 'solid' or 'dashed'
    this.hoverText = hoverText;
    this.group = null;
    this.tooltip = document.getElementById('tooltip');
    
    this.draw();
    
    // Redraw on window resize
    window.addEventListener('resize', () => this.draw());
    // Also redraw on scroll
    window.addEventListener('scroll', () => this.draw());
  }
  
  getCellRect(cell) {
    return cell.getBoundingClientRect();
  }
  
  // Find the closest point on the border of a rectangle to another point
  getClosestPointOnBorder(rect, targetX, targetY) {
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    
    // Calculate angle from center to target
    const angle = Math.atan2(targetY - centerY, targetX - centerX);
    
    // Determine which edge the line intersects
    const absAngle = Math.abs(angle);
    const topBottomThreshold = Math.atan2(rect.height / 2, rect.width / 2);
    
    let x, y;
    
    if (absAngle < topBottomThreshold) {
      // Right edge
      x = rect.right;
      y = centerY + (rect.width / 2) * Math.tan(angle);
    } else if (absAngle > Math.PI - topBottomThreshold) {
      // Left edge
      x = rect.left;
      y = centerY - (rect.width / 2) * Math.tan(angle);
    } else if (angle > 0) {
      // Bottom edge
      y = rect.bottom;
      x = centerX + (rect.height / 2) / Math.tan(angle);
    } else {
      // Top edge
      y = rect.top;
      x = centerX - (rect.height / 2) / Math.tan(angle);
    }
    
    return { x, y };
  }
  
  draw() {
    // Remove existing arrow if any
    if (this.group) {
      this.group.remove();
    }
    
    // Create new group for this arrow
    this.group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    
    const rect1 = this.getCellRect(this.cell1);
    const rect2 = this.getCellRect(this.cell2);
    
    // Get centers for initial calculation
    const center1 = {
      x: rect1.left + rect1.width / 2,
      y: rect1.top + rect1.height / 2
    };
    const center2 = {
      x: rect2.left + rect2.width / 2,
      y: rect2.top + rect2.height / 2
    };
    
    // Find closest points on borders
    const pos1 = this.getClosestPointOnBorder(rect1, center2.x, center2.y);
    const pos2 = this.getClosestPointOnBorder(rect2, center1.x, center1.y);
    
    // Calculate angle for rotation
    const angle = Math.atan2(pos2.y - pos1.y, pos2.x - pos1.x) * 180 / Math.PI;
    
    // Draw main line
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', pos1.x);
    line.setAttribute('y1', pos1.y);
    line.setAttribute('x2', pos2.x);
    line.setAttribute('y2', pos2.y);
    line.setAttribute('class', `arrow-line ${this.style === 'dashed' ? 'dashed' : ''}`);
    this.group.appendChild(line);
    
    // Draw arrowheads at both ends
    this.drawArrowhead(pos1.x, pos1.y, angle + 180);
    this.drawArrowhead(pos2.x, pos2.y, angle);
    
    // Draw label in the middle, rotated to follow arrow direction
    const midX = (pos1.x + pos2.x) / 2;
    const midY = (pos1.y + pos2.y) / 2;

    // Create background rectangle for label
    const labelBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('class', 'arrow-label');
    label.textContent = this.labelText;

    // Check if arrow is exactly vertical (cells directly under/over each other)
    const isVertical = Math.abs(pos1.x - pos2.x) < 10; // Using small threshold for floating point comparison

    // Determine text rotation angle and position with increased offset
    let labelRotationAngle;
    let labelX = midX;
    let labelY = midY;
    const labelOffset = 25; // Increased offset from arrow line

    if (isVertical) {
      // For vertical arrows, keep text horizontal and position it to the right
      labelRotationAngle = 0;
      labelX = midX + 60; // Increased offset to the right of the arrow
      labelY = midY;
    } else {
      // For non-vertical arrows, offset perpendicular to the arrow
      labelRotationAngle = angle;
      if (angle > 90 || angle < -90) {
        labelRotationAngle = angle + 180;
      }

      // Calculate perpendicular offset
      const perpAngle = (angle - 90) * Math.PI / 180;
      labelX = midX + labelOffset * Math.cos(perpAngle);
      labelY = midY + labelOffset * Math.sin(perpAngle);
    }
    
    label.setAttribute('x', labelX);
    label.setAttribute('y', labelY);
    label.setAttribute('transform', `rotate(${labelRotationAngle}, ${labelX}, ${labelY})`);
    
    // Add hover functionality if hoverText is provided
    if (this.hoverText) {
      label.addEventListener('mouseenter', (e) => this.showTooltip(e));
      label.addEventListener('mousemove', (e) => this.moveTooltip(e));
      label.addEventListener('mouseleave', () => this.hideTooltip());
    }
    
    // Calculate label dimensions for background (approximate)
    const labelWidth = this.labelText.length * 8 + 10;
    const labelHeight = 20;
    
    labelBg.setAttribute('x', labelX - labelWidth / 2);
    labelBg.setAttribute('y', labelY - labelHeight / 2);
    labelBg.setAttribute('width', labelWidth);
    labelBg.setAttribute('height', labelHeight);
    labelBg.setAttribute('class', 'arrow-label-bg');
    labelBg.setAttribute('transform', `rotate(${labelRotationAngle}, ${labelX}, ${labelY})`);
    
    if (this.hoverText) {
      labelBg.addEventListener('mouseenter', (e) => this.showTooltip(e));
      labelBg.addEventListener('mousemove', (e) => this.moveTooltip(e));
      labelBg.addEventListener('mouseleave', () => this.hideTooltip());
    }

    // Don't append the background rectangle - no white background needed
    // this.group.appendChild(labelBg);
    this.group.appendChild(label);
    this.svg.appendChild(this.group);
  }
  
  drawArrowhead(x, y, angle) {
    const arrowhead = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    const size = 10;
    
    // Create arrowhead pointing right, then rotate
    const points = [
      [x, y],
      [x - size, y - size/2],
      [x - size, y + size/2]
    ];
    
    // Rotate points around (x, y)
    const rad = angle * Math.PI / 180;
    const rotatedPoints = points.map(([px, py]) => {
      const dx = px - x;
      const dy = py - y;
      return [
        x + dx * Math.cos(rad) - dy * Math.sin(rad),
        y + dx * Math.sin(rad) + dy * Math.cos(rad)
      ];
    });
    
    arrowhead.setAttribute('points', rotatedPoints.map(p => p.join(',')).join(' '));
    arrowhead.setAttribute('class', 'arrow-head');
    this.group.appendChild(arrowhead);
  }
  
  showTooltip(e) {
    this.tooltip.textContent = this.hoverText;
    this.tooltip.classList.add('active');
    this.moveTooltip(e);
  }
  
  moveTooltip(e) {
    const offset = 25; // Increased offset to prevent interference with arrow
    this.tooltip.style.left = (e.clientX + offset) + 'px';
    this.tooltip.style.top = (e.clientY + offset) + 'px';
  }
  
  hideTooltip() {
    this.tooltip.classList.remove('active');
  }
}