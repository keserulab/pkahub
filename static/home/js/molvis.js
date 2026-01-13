/**
 * MolVis - Molecular Visualization Component
 *
 * A JavaScript component for visualizing molecular charge states, microspecies,
 * and pKa transitions in a vertical layout with bidirectional arrows.
 */

class MolVis {
    /**
     * Create a new MolVis visualization
     * @param {string} containerId - ID of the container element
     * @param {Object} data - MolVis input data (from internaldict_to_msviz_input)
     * @param {Object} options - Optional configuration
     * @param {Function} options.imageSourceCallback - Optional callback function to generate image URLs dynamically
     *                                                   Receives (microspecies) and returns image URL or data URI
     */
    constructor(containerId, data, options = {}) {
        this.containerId = containerId;
        this.data = data;
        this.options = options;
        this.container = document.getElementById(containerId);

        if (!this.container) {
            console.error(`MolVis: Container with id '${containerId}' not found`);
            return;
        }

        this.arrows = [];
        this.chargeStateElements = {};

        this.init();
    }

    /**
     * Initialize the visualization
     */
    init() {
        // Clear container
        this.container.innerHTML = '';

        // Add MolVis class to container
        this.container.classList.add('molvis-container');

        // Create SVG layer for arrows
        this.svgLayer = this.createSVGLayer();
        this.container.appendChild(this.svgLayer);

        // Create content layer
        this.contentLayer = document.createElement('div');
        this.contentLayer.className = 'molvis-content';
        this.container.appendChild(this.contentLayer);

        // Render charge states and microspecies
        this.renderChargeStates();

        // Render arrows after a short delay to ensure DOM is ready
        setTimeout(() => {
            this.renderArrows();
            this.setupEventListeners();
        }, 100);
    }

    /**
     * Create SVG layer for arrows
     */
    createSVGLayer() {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.classList.add('molvis-svg-layer');
        svg.style.position = 'absolute';
        svg.style.top = '0';
        svg.style.left = '0';
        svg.style.width = '100%';
        svg.style.height = '100%';
        svg.style.pointerEvents = 'none';
        svg.style.zIndex = '1';
        return svg;
    }

    /**
     * Render all charge states and their microspecies
     */
    renderChargeStates() {
        this.data.charge_states.forEach((chargeState, index) => {
            const chargeRow = this.createChargeStateRow(chargeState, index);
            this.contentLayer.appendChild(chargeRow);
        });
    }

    /**
     * Create a single charge state row with microspecies
     */
    createChargeStateRow(chargeState, index) {
        const row = document.createElement('div');
        row.className = 'molvis-charge-row';
        row.dataset.charge = chargeState.charge;

        // Left section: Charge state label
        const leftSection = document.createElement('div');
        leftSection.className = 'molvis-charge-label';
        leftSection.id = `molvis-charge-${this.containerId}-${chargeState.charge}`;

        const chargeText = document.createElement('div');
        chargeText.className = 'molvis-charge-text';
        chargeText.textContent = `Charge State: ${chargeState.charge_label}`;
        leftSection.appendChild(chargeText);

        // Store reference for arrow positioning
        this.chargeStateElements[chargeState.charge] = leftSection;

        // Right section: Microspecies
        const rightSection = document.createElement('div');
        rightSection.className = 'molvis-microspecies-section';

        chargeState.microspecies.forEach(ms => {
            const msElement = this.createMicrospeciesElement(ms);
            rightSection.appendChild(msElement);
        });

        row.appendChild(leftSection);
        row.appendChild(rightSection);

        return row;
    }

    /**
     * Create a single microspecies element
     */
    createMicrospeciesElement(microspecies) {
        const msContainer = document.createElement('div');
        msContainer.className = 'molvis-microspecies';
        msContainer.dataset.msId = microspecies.id;

        // Image
        const img = document.createElement('img');

        // Determine image source
        let imageSrc;
        if (this.options.imageSourceCallback) {
            // Use callback to generate image source dynamically
            imageSrc = this.options.imageSourceCallback(microspecies);
        } else if (microspecies.image_path) {
            // Debug logging
            console.log('MolVis image_path:', microspecies.image_path);

            // Handle both full paths and filenames - if it's just a filename, prepend the molimages path
            // Check for both forward slash and backslash to handle Windows paths
            const imagePath = (microspecies.image_path.includes('/') || microspecies.image_path.includes('\\'))
                ? microspecies.image_path
                : `home/molimages/${microspecies.image_path}`;

            imageSrc = `/static/${imagePath}`;
            console.log('MolVis imageSrc:', imageSrc);
        } else {
            // No image path and no callback - use placeholder
            console.log('MolVis: No image_path found for microspecies', microspecies.id);
            imageSrc = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="%23f0f0f0"/><text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="%23999">No Image</text></svg>';
        }

        img.src = imageSrc;
        img.alt = `Microspecies ${microspecies.id}`;
        img.className = 'molvis-microspecies-image';
        img.onerror = function() {
            console.error('MolVis: Image failed to load:', this.src);
            this.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="%23f0f0f0"/><text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="%23999">Image Error</text></svg>';
        };

        // Population label
        const popLabel = document.createElement('div');
        popLabel.className = 'molvis-population-label';
        popLabel.textContent = microspecies.relative_population_percent;

        msContainer.appendChild(img);
        msContainer.appendChild(popLabel);

        return msContainer;
    }

    /**
     * Render all transition arrows
     */
    renderArrows() {
        // Clear existing arrows
        this.svgLayer.innerHTML = '';
        this.arrows = [];

        // Create arrows for each transition
        this.data.transitions.forEach(transition => {
            const arrow = this.createArrow(transition);
            if (arrow) {
                this.arrows.push(arrow);
            }
        });
    }

    /**
     * Create a single bidirectional arrow for a transition
     */
    createArrow(transition) {
        const sourceElement = this.chargeStateElements[transition.charge_pre];
        const targetElement = this.chargeStateElements[transition.charge_post];

        if (!sourceElement || !targetElement) {
            console.warn(`MolVis: Could not find elements for transition ${transition.charge_pre} -> ${transition.charge_post}`);
            return null;
        }

        // Get positions
        const sourceRect = sourceElement.getBoundingClientRect();
        const targetRect = targetElement.getBoundingClientRect();
        const containerRect = this.container.getBoundingClientRect();

        // Calculate positions relative to container
        const x1 = sourceRect.left + sourceRect.width / 2 - containerRect.left;
        const y1 = sourceRect.bottom - containerRect.top;
        const x2 = targetRect.left + targetRect.width / 2 - containerRect.left;
        const y2 = targetRect.top - containerRect.top;

        // Create arrow group
        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.classList.add('molvis-arrow');
        group.dataset.chargePre = transition.charge_pre;
        group.dataset.chargePost = transition.charge_post;

        // Determine arrow style based on whether we have data
        const strokeStyle = transition.has_data ? 'solid' : 'dashed';
        const strokeDasharray = transition.has_data ? 'none' : '5,5';

        // Create line
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', x1);
        line.setAttribute('y1', y1);
        line.setAttribute('x2', x2);
        line.setAttribute('y2', y2);
        line.setAttribute('stroke', '#333');
        line.setAttribute('stroke-width', '2');
        line.setAttribute('stroke-dasharray', strokeDasharray);
        line.setAttribute('marker-end', 'url(#arrowhead)');
        line.setAttribute('marker-start', 'url(#arrowhead-reverse)');

        // Create label background
        const labelX = (x1 + x2) / 2;
        const labelY = (y1 + y2) / 2;

        const labelBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        labelBg.setAttribute('x', labelX - 60);
        labelBg.setAttribute('y', labelY - 12);
        labelBg.setAttribute('width', '120');
        labelBg.setAttribute('height', '24');
        labelBg.setAttribute('fill', 'white');
        labelBg.setAttribute('stroke', '#333');
        labelBg.setAttribute('stroke-width', '1');
        labelBg.setAttribute('rx', '4');

        // Create label text
        const labelText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        labelText.setAttribute('x', labelX);
        labelText.setAttribute('y', labelY);
        labelText.setAttribute('text-anchor', 'middle');
        labelText.setAttribute('dominant-baseline', 'middle');
        labelText.setAttribute('font-size', '12');
        labelText.setAttribute('font-family', 'Arial, sans-serif');
        labelText.textContent = transition.label;

        // Add tooltip for detailed pKa information
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        if (transition.has_data) {
            const tooltipLines = transition.pka_values.map(pka =>
                `${pka.pka_value} (${pka.data_source || 'Unknown'})`
            ).join('\n');
            title.textContent = tooltipLines;
        } else {
            title.textContent = 'No experimental data available for this transition';
        }

        group.appendChild(line);
        group.appendChild(labelBg);
        group.appendChild(labelText);
        group.appendChild(title);

        this.svgLayer.appendChild(group);

        return {
            element: group,
            transition: transition,
            sourceElement: sourceElement,
            targetElement: targetElement
        };
    }

    /**
     * Setup event listeners for responsive behavior
     */
    setupEventListeners() {
        // Redraw arrows on window resize
        window.addEventListener('resize', () => this.handleResize());

        // Redraw arrows on scroll (if container is scrollable)
        window.addEventListener('scroll', () => this.handleScroll());
    }

    /**
     * Handle window resize
     */
    handleResize() {
        this.renderArrows();
    }

    /**
     * Handle scroll
     */
    handleScroll() {
        this.renderArrows();
    }

    /**
     * Update the visualization with new data
     */
    update(newData) {
        this.data = newData;
        this.init();
    }

    /**
     * Destroy the visualization and clean up
     */
    destroy() {
        window.removeEventListener('resize', this.handleResize);
        window.removeEventListener('scroll', this.handleScroll);
        this.container.innerHTML = '';
        this.arrows = [];
        this.chargeStateElements = {};
    }
}

// Create arrow markers (to be added to the first SVG on the page)
function createArrowMarkers() {
    // Check if markers already exist
    if (document.getElementById('molvis-arrow-markers')) {
        return;
    }

    // Create a hidden SVG to hold marker definitions
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    defs.id = 'molvis-arrow-markers';
    defs.style.position = 'absolute';
    defs.style.width = '0';
    defs.style.height = '0';

    const defsElement = document.createElementNS('http://www.w3.org/2000/svg', 'defs');

    // Arrowhead marker (pointing right/down)
    const arrowhead = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    arrowhead.id = 'arrowhead';
    arrowhead.setAttribute('markerWidth', '10');
    arrowhead.setAttribute('markerHeight', '10');
    arrowhead.setAttribute('refX', '9');
    arrowhead.setAttribute('refY', '3');
    arrowhead.setAttribute('orient', 'auto');
    arrowhead.setAttribute('markerUnits', 'strokeWidth');

    const arrowPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    arrowPath.setAttribute('d', 'M0,0 L0,6 L9,3 z');
    arrowPath.setAttribute('fill', '#333');

    arrowhead.appendChild(arrowPath);

    // Reverse arrowhead marker (pointing left/up)
    const arrowheadReverse = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    arrowheadReverse.id = 'arrowhead-reverse';
    arrowheadReverse.setAttribute('markerWidth', '10');
    arrowheadReverse.setAttribute('markerHeight', '10');
    arrowheadReverse.setAttribute('refX', '0');
    arrowheadReverse.setAttribute('refY', '3');
    arrowheadReverse.setAttribute('orient', 'auto');
    arrowheadReverse.setAttribute('markerUnits', 'strokeWidth');

    const arrowPathReverse = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    arrowPathReverse.setAttribute('d', 'M9,0 L9,6 L0,3 z');
    arrowPathReverse.setAttribute('fill', '#333');

    arrowheadReverse.appendChild(arrowPathReverse);

    defsElement.appendChild(arrowhead);
    defsElement.appendChild(arrowheadReverse);
    defs.appendChild(defsElement);

    document.body.appendChild(defs);
}

// Initialize arrow markers when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createArrowMarkers);
} else {
    createArrowMarkers();
}
