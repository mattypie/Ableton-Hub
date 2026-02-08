"""Similarities panel widget showing similar projects based on analysis."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...database import Project, get_session
from ...services.similarity_analyzer import SimilarityAnalyzer
from ..theme import AbletonTheme


class RecommendationsPanel(QWidget):
    """Panel showing project similarity analysis."""

    project_selected = pyqtSignal(int)  # Emitted when a project is selected

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._analyzer = SimilarityAnalyzer()
        self._current_project_id: int | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Similarities")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_similar)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Explanation section
        explanation_group = QGroupBox("How Project Similarity Works")
        explanation_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {AbletonTheme.COLORS['border']};
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        explanation_layout = QVBoxLayout(explanation_group)
        explanation_layout.setSpacing(8)

        explanation = QLabel(
            "Projects are compared using a <b>weighted hybrid similarity</b> score:<br><br>"
            "&#8226; <b>Feature Vectors (35%)</b>: Cosine similarity of project feature vectors "
            "(track counts, plugin/device counts, tempo, arrangement length, ASD clip data). "
            "Computed during scanning and stored in the database.<br>"
            "&#8226; <b>Plugins (20%)</b>: Jaccard set similarity of VST/AU plugins "
            "(e.g., both use Serum and FabFilter Pro-Q).<br>"
            "&#8226; <b>Devices (15%)</b>: Jaccard set similarity of Ableton devices "
            "(e.g., both use Wavetable and Compressor).<br>"
            "&#8226; <b>Tempo (15%)</b>: BPM proximity (identical = 100%, >50 BPM apart = 0%).<br>"
            "&#8226; <b>Structure (15%)</b>: Track counts, audio/MIDI ratio, arrangement length.<br>"
            "<br>"
            "<b>Jaccard Formula:</b> |A &#8745; B| / |A &#8746; B|<br>"
            "Example: Project A uses [Serum, Massive, Pro-Q], Project B uses [Serum, Pro-Q, Ozone]<br>"
            "&#8594; Intersection = 2 (Serum, Pro-Q), Union = 4 &#8594; Jaccard = 2/4 = 50%"
        )
        explanation.setStyleSheet(
            f"color: {AbletonTheme.COLORS['text_secondary']}; font-size: 11px;"
        )
        explanation.setWordWrap(True)
        explanation_layout.addWidget(explanation)

        layout.addWidget(explanation_group)

        # Project selector
        selector_layout = QHBoxLayout()

        selector_label = QLabel("Compare Project:")
        selector_label.setStyleSheet("font-weight: bold;")
        selector_layout.addWidget(selector_label)

        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(300)
        self.project_combo.currentIndexChanged.connect(self._on_project_combo_changed)
        selector_layout.addWidget(self.project_combo)

        selector_layout.addStretch()

        layout.addLayout(selector_layout)

        # Populate combo box
        self._project_id_map: dict[int, int] = {}  # combo index -> project id
        self._populate_project_combo()

        # Similar projects group
        similar_group = QGroupBox("Similar Projects")
        similar_layout = QVBoxLayout(similar_group)

        self.similar_list = QListWidget()
        self.similar_list.itemDoubleClicked.connect(self._on_project_double_click)
        similar_layout.addWidget(self.similar_list)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        similar_layout.addWidget(self.progress_bar)

        layout.addWidget(similar_group)

        layout.addStretch()

    def set_project(self, project_id: int) -> None:
        """Set the current project and load similar projects."""
        self._current_project_id = project_id
        self._select_combo_by_project_id(project_id)
        self._refresh_similar()

    def _populate_project_combo(self) -> None:
        """Populate the project combo box with all projects."""
        # Block signals to prevent triggering change event during population
        self.project_combo.blockSignals(True)

        current_project_id = self._current_project_id
        self.project_combo.clear()
        self._project_id_map.clear()

        # Add placeholder
        self.project_combo.addItem("-- Select a project --")
        self._project_id_map[0] = None

        session = get_session()
        try:
            projects = session.query(Project).order_by(Project.name).all()

            selected_index = 0
            for idx, project in enumerate(projects, start=1):
                display_name = project.name
                if project.location:
                    display_name = f"{project.name} ({project.location.name})"

                self.project_combo.addItem(display_name)
                self._project_id_map[idx] = project.id

                # Check if this was the previously selected project
                if project.id == current_project_id:
                    selected_index = idx

            # Restore selection
            if selected_index > 0:
                self.project_combo.setCurrentIndex(selected_index)

        finally:
            session.close()

        self.project_combo.blockSignals(False)

    def _on_project_combo_changed(self, index: int) -> None:
        """Handle project combo box selection change."""
        project_id = self._project_id_map.get(index)
        if project_id is not None:
            self._current_project_id = project_id
            self._refresh_similar()
        else:
            # Placeholder selected - clear results
            self._current_project_id = None
            self.similar_list.clear()
            self.similar_list.addItem(QListWidgetItem("Select a project to see similar projects"))

    def _select_combo_by_project_id(self, project_id: int) -> None:
        """Select the combo box item matching the given project ID."""
        for index, pid in self._project_id_map.items():
            if pid == project_id:
                self.project_combo.blockSignals(True)
                self.project_combo.setCurrentIndex(index)
                self.project_combo.blockSignals(False)
                return

    def _refresh_similar(self) -> None:
        """Refresh similar projects for the current project."""
        if not self._current_project_id:
            self.similar_list.clear()
            self.similar_list.addItem(QListWidgetItem("Select a project to see similar projects"))
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        try:
            session = get_session()
            try:
                project = session.query(Project).get(self._current_project_id)
                if not project:
                    return

                # Convert to dict format
                project_dict = self._project_to_dict(project)

                # Get all other projects
                all_projects = (
                    session.query(Project).filter(Project.id != self._current_project_id).all()
                )

                if not all_projects:
                    self.similar_list.clear()
                    self.similar_list.addItem(QListWidgetItem("No other projects found"))
                    self.progress_bar.setVisible(False)
                    return

                candidate_dicts = [self._project_to_dict(p) for p in all_projects]

                # Find similar projects
                similar = self._analyzer.find_similar_projects(
                    reference_project=project_dict,
                    candidate_projects=candidate_dicts,
                    top_n=15,
                    min_similarity=0.3,
                )

                # Populate similar projects list
                self.similar_list.clear()
                if similar:
                    for sim_project in similar:
                        score_percent = int(sim_project.similarity_score * 100)
                        item_text = f"{sim_project.project_name} ({score_percent}% similar)"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.ItemDataRole.UserRole, sim_project.project_id)

                        # Build tooltip with score breakdown
                        tooltip_parts = [f"Overall Similarity: {score_percent}%"]
                        if sim_project.similarity_result:
                            r = sim_project.similarity_result
                            tooltip_parts.append(
                                f"  Feature: {r.feature_similarity:.0%}  "
                                f"Plugins: {r.plugin_similarity:.0%}  "
                                f"Devices: {r.device_similarity:.0%}"
                            )
                            tooltip_parts.append(
                                f"  Tempo: {r.tempo_similarity:.0%}  "
                                f"Structure: {r.structural_similarity:.0%}"
                            )
                            explanation = self._analyzer.get_similarity_explanation(r)
                            tooltip_parts.append(explanation)
                        item.setToolTip("\n".join(tooltip_parts))

                        self.similar_list.addItem(item)
                else:
                    self.similar_list.addItem(
                        QListWidgetItem("No similar projects found (min similarity: 30%)")
                    )

            finally:
                session.close()

            self.progress_bar.setVisible(False)

        except Exception as e:
            self.similar_list.clear()
            self.similar_list.addItem(QListWidgetItem(f"Error: {str(e)}"))
            self.progress_bar.setVisible(False)

    def _project_to_dict(self, project: Project) -> dict:
        """Convert Project model to dictionary."""
        return {
            "id": project.id,
            "name": project.name,
            "plugins": project.get_plugins_list(),
            "devices": project.get_devices_list(),
            "tempo": project.tempo,
            "track_count": project.track_count or 0,
            "audio_tracks": getattr(project, "audio_tracks", 0) or 0,
            "midi_tracks": getattr(project, "midi_tracks", 0) or 0,
            "arrangement_length": project.arrangement_length or 0,
            "als_path": project.file_path,
            "feature_vector": (
                project.get_feature_vector_list()
                if hasattr(project, "get_feature_vector_list")
                else None
            ),
        }

    def _on_project_double_click(self, item: QListWidgetItem) -> None:
        """Handle double-click on a project."""
        project_id = item.data(Qt.ItemDataRole.UserRole)
        if project_id:
            self.project_selected.emit(project_id)
