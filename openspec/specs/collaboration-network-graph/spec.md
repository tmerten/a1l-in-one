### Requirement: Graph renders nodes for each collaborator
The system SHALL render a force-directed network graph where each person who appears in the review matrix (as either reviewer or author) is represented as a circular node with their initials.

#### Scenario: Graph displays all participants
- **WHEN** the collaboration API returns a review_matrix with entries for persons A, B, and C
- **THEN** the graph renders exactly three nodes, one for each person

#### Scenario: Person appearing only as author is included
- **WHEN** person D appears only as an author (is reviewed by others but reviews nobody)
- **THEN** person D is still rendered as a node in the graph

#### Scenario: Node shows initials
- **WHEN** a node is rendered for a person with display name "Jane Doe"
- **THEN** the node displays the initial "J" inside the circle

### Requirement: Graph renders edges for collaboration pairs
The system SHALL render edges (lines) between nodes that have a review relationship, with edge thickness proportional to the collaboration count.

#### Scenario: Undirected edge between collaborating pair
- **WHEN** the graph is in undirected mode and A reviewed B 3 times and B reviewed A 2 times
- **THEN** a single undirected edge connects A and B with a weight of 5

#### Scenario: Edge thickness reflects weight
- **WHEN** edge A-B has weight 10 and edge C-D has weight 2
- **THEN** edge A-B is visually thicker than edge C-D

#### Scenario: Edge weight label on hover
- **WHEN** the user hovers over an edge
- **THEN** a numeric label showing the collaboration count is displayed at the edge midpoint

### Requirement: Directed mode toggle
The system SHALL provide a toggle within the graph component to switch between undirected (default) and directed edge rendering.

#### Scenario: Toggle to directed mode
- **WHEN** the user activates the directed mode toggle
- **THEN** edges become arrows showing direction (reviewer -> author) and bidirectional pairs show two separate arrows

#### Scenario: Directed mode shows individual counts
- **WHEN** in directed mode and A reviewed B 3 times and B reviewed A 2 times
- **THEN** two arrows are displayed: A->B with weight 3 and B->A with weight 2

#### Scenario: Default mode is undirected
- **WHEN** the graph component first renders
- **THEN** edges are displayed in undirected mode without arrows

### Requirement: Graph integrates into Collaboration section view toggle
The system SHALL add a "graph" option to the existing Collaboration section view toggle alongside "cards" and "charts".

#### Scenario: User selects graph view
- **WHEN** the user clicks the graph view option in the Collaboration section toggle
- **THEN** the collaboration network graph is displayed in place of the metric cards or bar chart

#### Scenario: Other views remain functional
- **WHEN** the user switches from graph view to cards view
- **THEN** the existing Review Pairs metric card is displayed as before

### Requirement: Nodes are draggable
The system SHALL allow users to drag nodes to manually adjust the graph layout.

#### Scenario: Drag a node
- **WHEN** the user clicks and drags a node to a new position
- **THEN** the node moves to the new position and connected edges update accordingly

#### Scenario: Layout stabilizes after drag
- **WHEN** the user releases a dragged node
- **THEN** the force simulation resettles with the node fixed at its new position

### Requirement: Node hover shows person name
The system SHALL display a tooltip with the person's full display name when hovering over a node.

#### Scenario: Hover reveals name
- **WHEN** the user hovers over a node for person "Jane Doe"
- **THEN** a tooltip displays "Jane Doe"

### Requirement: Graph respects existing filters
The system SHALL use the current timeframe and project/datasource filters when rendering the graph, consistent with the other collaboration views.

#### Scenario: Timeframe filter changes graph data
- **WHEN** the user changes the timeframe from "last 30 days" to "last 7 days"
- **THEN** the graph updates to show only collaboration pairs from the last 7 days

#### Scenario: Project filter limits graph scope
- **WHEN** the user selects a specific project in the datasource filter
- **THEN** the graph shows only review pairs from that project

### Requirement: Empty state handling
The system SHALL display appropriate feedback when there is no collaboration data to graph.

#### Scenario: No review data in period
- **WHEN** the review_matrix is empty for the selected timeframe
- **THEN** the graph area displays a message "No collaboration data for this period"

#### Scenario: Single person with no edges
- **WHEN** only one person has review activity (self-reviews are excluded)
- **THEN** a single node is displayed without any edges
