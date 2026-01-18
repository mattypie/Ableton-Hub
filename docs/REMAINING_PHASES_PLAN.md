---
name: Remaining Phases Plan - Ableton Hub
overview: Comprehensive plan for Phases 4-7 of Ableton Hub, with primary focus on Phase 5 (Deep Project Analysis) to extract plugin usage patterns, project similarity metrics, and workflow insights. Includes research on GitHub packages for enhanced .als file parsing and metadata extraction.
todos:
  - id: phase4-pack-scanner
    content: 'Phase 4: Implement pack scanner service to detect installed Ableton Packs'
    status: pending
  - id: phase4-pack-db
    content: 'Phase 4: Add Pack and ProjectPack database models'
    status: pending
  - id: phase4-pack-ui
    content: 'Phase 4: Create pack browser UI widget'
    status: pending
    dependencies:
      - phase4-pack-scanner
      - phase4-pack-db
  - id: phase5-parser-enhance
    content: 'Phase 5: Enhance ALS parser with lxml and deeper XML analysis (device chains, clips, routing)'
    status: pending
  - id: phase5-plugin-analyzer
    content: 'Phase 5: Implement plugin analyzer service for usage patterns and statistics'
    status: pending
    dependencies:
      - phase5-parser-enhance
  - id: phase5-plugin-db
    content: 'Phase 5: Add PluginUsage database model and extend Project model with plugin chain data'
    status: pending
  - id: phase5-plugin-ui
    content: 'Phase 5: Create plugin usage dashboard UI widget'
    status: pending
    dependencies:
      - phase5-plugin-analyzer
      - phase5-plugin-db
  - id: phase5-similarity-analyzer
    content: 'Phase 5: Implement similarity analyzer service with tempo, device, plugin, and structure comparison'
    status: pending
    dependencies:
      - phase5-parser-enhance
  - id: phase5-similarity-db
    content: 'Phase 5: Add ProjectSimilarity database model for caching similarity scores'
    status: pending
  - id: phase5-similarity-ui
    content: 'Phase 5: Add similarity visualization to project details dialog'
    status: pending
    dependencies:
      - phase5-similarity-analyzer
      - phase5-similarity-db
  - id: phase5-workflow-analyzer
    content: 'Phase 5: Implement workflow analyzer service for lifecycle and productivity metrics'
    status: pending
  - id: phase5-workflow-db
    content: 'Phase 5: Add WorkflowMetrics database model for time-series analytics'
    status: pending
  - id: phase5-workflow-ui
    content: 'Phase 5: Create workflow analytics dashboard UI widget'
    status: pending
    dependencies:
      - phase5-workflow-analyzer
      - phase5-workflow-db
  - id: phase5-project-details-enhance
    content: 'Phase 5: Enhance project details dialog with plugin, similarity, and workflow tabs'
    status: pending
    dependencies:
      - phase5-plugin-ui
      - phase5-similarity-ui
      - phase5-workflow-ui
  - id: phase6-feature-extraction
    content: 'Phase 6: Build feature extraction pipeline from project metadata'
    status: pending
    dependencies:
      - phase5-similarity-analyzer
  - id: phase6-clustering
    content: 'Phase 6: Implement ML clustering algorithm (K-means/DBSCAN) for project grouping'
    status: pending
    dependencies:
      - phase6-feature-extraction
  - id: phase6-recommendations
    content: 'Phase 6: Build recommendation engine using content-based filtering'
    status: pending
    dependencies:
      - phase6-feature-extraction
  - id: phase7-osc-research
    content: 'Phase 7: Research and test OSC connection to Ableton Live'
    status: pending
  - id: phase7-live-integration
    content: 'Phase 7: Implement Live connection service with current project detection'
    status: pending
    dependencies:
      - phase7-osc-research
---

# Remaining Phases Implementation Plan - Ableton Hub

## Overview

This plan outlines the implementation of Phases 4-7, with **primary focus on Phase 5 (Deep Project Analysis)** to extract valuable insights including plugin usage patterns, project similarity detection, and workflow analytics. The plan includes research on GitHub packages for enhanced Ableton Live project file parsing.

## Current State Assessment

**Completed (Phases 1-3):**
- Basic project discovery and scanning
- Collection management (albums, EPs, sessions)
- Export tracking and mapping
- Tagging and search
- File system watching
- Ableton Link network monitoring
- Basic ALS parsing (plugins, devices, tempo, tracks, samples)
- Smart Collections, Duplicate Detection, Health Dashboard (Phase 2.5)
- Live installation detection and launcher

**Current ALS Parser Capabilities:**
- Extracts: plugins (VST/AU), devices, tempo, time signature, track counts, arrangement length, Ableton version, sample references, automation detection
- Located in: `[ableton_hub/src/services/als_parser.py](ableton_hub/src/services/als_parser.py)`
- Uses: `gzip` + `xml.etree.ElementTree` (standard library)

## Phase Goals & Priorities

### Phase 4: Pack Management
**Goal**: Track and organize Ableton Packs, detect updates, show usage statistics

### Phase 5: Deep Project Analysis (PRIMARY FOCUS)
**Goal**: Extract comprehensive insights from project metadata, focusing on:
- **Plugin Usage Patterns**: Track which plugins are used most, plugin combinations, plugin availability
- **Project Similarity**: Detect similar projects by tempo, devices, plugins, structure
- **Workflow Analytics**: Analyze project creation patterns, modification frequency, completion metrics

### Phase 6: AI/ML Analysis
**Goal**: Intelligent clustering, recommendations, and pattern recognition

### Phase 7: Live Integration
**Goal**: Real-time connection to running Ableton Live instance

## Phase 4: Pack Management (Week 10-11)

### Goals
- Scan and catalog installed Ableton Packs
- Track pack versions and detect updates
- Show pack usage per project
- Organize packs by category

### Implementation Tasks

1. **Pack Scanner Service** (`src/services/pack_scanner.py`)
   - Scan default Ableton library locations:
     - Windows: `%USERPROFILE%\Documents\Ableton\User Library\`
     - Mac: `~/Music/Ableton/User Library/`
   - Parse pack manifest files (`.alp` files or pack metadata)
   - Extract: pack name, version, category, size, installation date

2. **Database Schema** (`src/database/models.py`)
   ```python
   class Pack(Base):
       id = Column(Integer, primary_key=True)
       name = Column(String(255), nullable=False)
       version = Column(String(50))
       category = Column(String(100))
       install_path = Column(String(1024))
       file_size = Column(Integer)
       installed_date = Column(DateTime)
       is_factory = Column(Boolean, default=False)
       is_favorite = Column(Boolean, default=False)
   
   class ProjectPack(Base):
       project_id = Column(Integer, ForeignKey("projects.id"))
       pack_id = Column(Integer, ForeignKey("packs.id"))
       usage_count = Column(Integer, default=1)
   ```

3. **Pack Management UI** (`src/ui/widgets/pack_browser.py`)
   - Grid view of installed packs
   - Filter by category, factory vs user
   - Show pack usage statistics
   - Update detection and notifications

4. **Pack Usage Tracking**
   - Link packs to projects via sample references
   - Show "Projects using this pack" view
   - Track pack usage frequency

### Deliverables
- Pack browser UI
- Pack version tracking
- Pack-to-project associations
- Update detection system

## Phase 5: Deep Project Analysis (PRIMARY - Week 12-16)

### Goals
Extract actionable insights focusing on:
1. **Plugin Usage Patterns**
2. **Project Similarity Detection**
3. **Workflow Analytics**

### 5.1 Enhanced ALS Parser

**Current Parser Limitations:**
- Basic plugin/device extraction (names only)
- Limited sample reference details
- No device chain analysis
- No clip/automation lane details
- No track routing information

**Enhancement Strategy:**

#### Option A: Enhance Existing Parser
- Extend `[ableton_hub/src/services/als_parser.py](ableton_hub/src/services/als_parser.py)` with deeper XML traversal
- Add device chain parsing (order, parameters)
- Extract clip information (length, loop points, warp settings)
- Parse track routing (sends, returns, group tracks)
- Extract automation lane details

#### Option B: Research GitHub Packages

**Recommended Libraries to Evaluate:**

1. **abletoolz** (https://github.com/elixirbeats/abletoolz)
   - Elixir-based, but may have Python bindings or inspiration
   - Check for Python port or API

2. **Custom XML Parser Enhancement**
   - Current `xml.etree.ElementTree` is sufficient but can be enhanced
   - Consider `lxml` for better XPath support and performance
   - Add structured parsing for complex nested elements

3. **Alternative: Build Specialized Parsers**
   - Create focused parsers for specific insights:
     - `plugin_analyzer.py` - Deep plugin analysis
     - `similarity_analyzer.py` - Project comparison
     - `workflow_analyzer.py` - Pattern detection

**Recommendation**: Enhance existing parser with `lxml` for better XPath queries and add specialized analysis modules.

### 5.2 Plugin Usage Analysis

**New Service**: `src/services/plugin_analyzer.py`

**Features:**
1. **Plugin Statistics**
   - Most used plugins across all projects
   - Plugin usage frequency per project
   - Plugin combinations (which plugins are used together)
   - Plugin availability checking (detect missing plugins)

2. **Plugin Chains Analysis**
   - Common device chain patterns
   - Track-level plugin usage
   - Return/master track plugin usage

3. **Database Schema Extensions**
   ```python
   # Add to Project model
   plugin_chains = Column(JSON, default=list)  # Structured plugin chains per track
   plugin_combinations = Column(JSON, default=list)  # Common plugin pairs
   
   # New table
   class PluginUsage(Base):
       plugin_name = Column(String(255), primary_key=True)
       usage_count = Column(Integer, default=0)
       projects_using = Column(JSON, default=list)  # Project IDs
       last_used = Column(DateTime)
   ```

4. **UI Components**
   - Plugin usage dashboard (`src/ui/widgets/plugin_dashboard.py`)
   - "Projects using this plugin" filter
   - Plugin availability warnings
   - Plugin combination suggestions

### 5.3 Project Similarity Detection

**New Service**: `src/services/similarity_analyzer.py`

**Similarity Metrics:**
1. **Tempo Similarity** (±5 BPM tolerance)
2. **Device Similarity** (Jaccard similarity on device sets)
3. **Plugin Similarity** (Jaccard similarity on plugin sets)
4. **Track Structure Similarity** (audio/MIDI/return track ratios)
5. **Time Signature Match**
6. **Arrangement Length Similarity**

**Implementation:**
```python
class SimilarityAnalyzer:
    def calculate_similarity(self, project1: Project, project2: Project) -> float:
        """Calculate similarity score (0-1) between two projects."""
        scores = []
        
        # Tempo similarity
        if project1.tempo and project2.tempo:
            tempo_diff = abs(project1.tempo - project2.tempo)
            tempo_score = max(0, 1 - (tempo_diff / 20))  # 20 BPM tolerance
            scores.append(tempo_score * 0.2)
        
        # Device similarity (Jaccard)
        devices1 = set(project1.devices or [])
        devices2 = set(project2.devices or [])
        if devices1 or devices2:
            device_score = len(devices1 & devices2) / len(devices1 | devices2)
            scores.append(device_score * 0.3)
        
        # Plugin similarity (Jaccard)
        plugins1 = set(project1.plugins or [])
        plugins2 = set(project2.plugins or [])
        if plugins1 or plugins2:
            plugin_score = len(plugins1 & plugins2) / len(plugins1 | plugins2)
            scores.append(plugin_score * 0.3)
        
        # Track structure similarity
        structure_score = self._compare_track_structure(project1, project2)
        scores.append(structure_score * 0.2)
        
        return sum(scores)
    
    def find_similar_projects(self, project: Project, threshold: float = 0.6) -> List[Tuple[Project, float]]:
        """Find projects similar to the given project."""
        # Implementation with database query optimization
```

**Database Schema:**
```python
class ProjectSimilarity(Base):
    project1_id = Column(Integer, ForeignKey("projects.id"))
    project2_id = Column(Integer, ForeignKey("projects.id"))
    similarity_score = Column(Float)
    similarity_factors = Column(JSON)  # Breakdown of similarity components
    calculated_date = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('project1_id', 'project2_id'),
        Index('idx_similarity_score', 'similarity_score'),
    )
```

**UI Components:**
- "Similar Projects" panel in project details
- Similarity graph visualization
- "Find similar" search feature
- Batch similarity calculation

### 5.4 Workflow Analytics

**New Service**: `src/services/workflow_analyzer.py`

**Analytics to Track:**
1. **Project Lifecycle**
   - Average time from creation to first export
   - Projects with multiple versions (v1, v2, final)
   - Projects never exported
   - Projects modified recently vs archived

2. **Workflow Patterns**
   - Most active time periods (creation/modification patterns)
   - Project modification frequency
   - Collection completion rates
   - Tag usage trends

3. **Productivity Metrics**
   - Projects per month/year
   - Average project size
   - Export frequency
   - Collection size distribution

**Database Schema:**
```python
class WorkflowMetrics(Base):
    metric_date = Column(DateTime, primary_key=True)
    projects_created = Column(Integer, default=0)
    projects_modified = Column(Integer, default=0)
    projects_exported = Column(Integer, default=0)
    collections_created = Column(Integer, default=0)
    total_projects = Column(Integer, default=0)
    total_collections = Column(Integer, default=0)
```

**UI Components:**
- Workflow dashboard (`src/ui/widgets/workflow_dashboard.py`)
- Timeline visualization
- Productivity charts
- Trend analysis

### 5.5 Enhanced Project Detail View

**Enhance**: `src/ui/dialogs/project_details.py`

**New Sections:**
1. **Plugin Analysis Tab**
   - List of plugins with usage count
   - Plugin chain visualization
   - Missing plugin warnings

2. **Similarity Tab**
   - Similar projects list
   - Similarity breakdown (why projects are similar)
   - "Open similar project" action

3. **Workflow Tab**
   - Project timeline (created, modified, exported)
   - Version history (if versioning implemented)
   - Related projects (stems, remixes)

### Deliverables
- Enhanced ALS parser with deeper XML analysis
- Plugin usage dashboard and analytics
- Project similarity detection and visualization
- Workflow analytics dashboard
- Enhanced project detail view with insights

## Phase 6: AI/ML Analysis (Week 17-20)

### Goals
- Project clustering by style/tempo/devices
- Recommendation engine ("similar to this project")
- Genre/style classification
- Device chain pattern recognition

### Implementation Tasks

1. **Feature Extraction Pipeline**
   - Extract numerical features from projects:
     - Tempo, time signature (encoded)
     - Device counts (one-hot encoded)
     - Plugin counts (one-hot encoded)
     - Track structure (ratios)
     - Arrangement length

2. **Clustering Algorithm**
   - Use scikit-learn for K-means or DBSCAN clustering
   - Group projects by similarity features
   - Visualize clusters in dashboard

3. **Recommendation Engine**
   - Content-based filtering using similarity scores
   - "Projects you might like" suggestions
   - Based on current project's features

4. **Genre Classification** (Optional)
   - Train classifier on user-tagged projects
   - Auto-suggest genre tags
   - Pattern recognition for common genres

### Dependencies
- Phase 5 completion (similarity analysis)
- scikit-learn library
- Sufficient project data for training

### Deliverables
- Project clustering visualization
- Recommendation system
- Genre/style classification (if data available)

## Phase 7: Live Integration (Week 21-22)

### Goals
- Real-time connection to running Ableton Live
- Detect currently open project
- Quick actions (open project, import settings)

### Implementation Tasks

1. **OSC Connection Research**
   - Research Ableton Live OSC API
   - Test connection to Live instance
   - Handle connection errors gracefully

2. **Live API Integration**
   - Option A: OSC (Open Sound Control) protocol
   - Option B: Max for Live bridge device
   - Option C: Python Live API (if available)

3. **Current Project Detection**
   - Poll Live for currently open project
   - Update UI to show "Currently open in Live"
   - Sync project metadata when Live saves

4. **Quick Actions**
   - "Open in Live" (already implemented via launcher)
   - "Import device chain from Live"
   - "Sync project metadata"

### Dependencies
- Ableton Live running
- OSC library (python-osc)
- Max for Live device (if using bridge approach)

### Deliverables
- Live connection service
- Current project detection
- Quick action integration

## Implementation Priority & Timeline

### Immediate (Phase 5 Focus)
1. **Week 12-13**: Enhance ALS parser, implement plugin analyzer
2. **Week 14**: Implement similarity detection
3. **Week 15**: Build workflow analytics
4. **Week 16**: Create dashboards and UI components

### Short-term (Phase 4)
5. **Week 10-11**: Pack management (can run parallel to Phase 5)

### Medium-term (Phase 6)
6. **Week 17-20**: AI/ML clustering and recommendations

### Long-term (Phase 7)
7. **Week 21-22**: Live integration (optional, lower priority)

## Technical Recommendations

### Parser Enhancement
- **Upgrade to `lxml`**: Better XPath support, performance
  ```python
  from lxml import etree
  # Enables: root.xpath('//PluginDevice')
  ```

### Database Optimizations
- Add indexes for similarity queries
- Cache similarity calculations
- Periodic batch processing for analytics

### Performance Considerations
- Background processing for similarity calculations
- Lazy loading of detailed project data
- Caching of parsed metadata

## Research Notes: GitHub Packages

**Current Finding**: No widely-used Python library specifically for Ableton Live .als parsing found. The current implementation using `gzip` + `xml.etree.ElementTree` (or `lxml`) is the standard approach.

**Recommendation**: 
- Enhance existing parser rather than replacing it
- Consider `lxml` for better XML handling
- Build specialized analysis modules on top of base parser
- If `abletoolz` (Elixir) has useful patterns, adapt them to Python

## Success Criteria

### Phase 5 Success Metrics
- [ ] Plugin usage dashboard shows accurate statistics
- [ ] Similarity detection finds related projects (>80% accuracy)
- [ ] Workflow analytics provide actionable insights
- [ ] Enhanced project detail view displays all new insights
- [ ] Performance: Similarity calculation completes in <5s for 1000 projects

### Overall Success
- [ ] All phases documented and ready for implementation
- [ ] Clear implementation path for each phase
- [ ] Dependencies identified and manageable
- [ ] User value clearly demonstrated

## Next Steps

1. **Review and approve this plan**
2. **Prioritize Phase 5 tasks** (plugin analysis, similarity, workflow)
3. **Begin Phase 5 implementation** with parser enhancement
4. **Iterate based on user feedback** on insights value
5. **Proceed to Phase 6/7** based on Phase 5 success
