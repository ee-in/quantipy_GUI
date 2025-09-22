# Quantipy Rake GUI

The experimental Tkinter GUI is designed to help analysts explore Quantipy's
rake weighting workflow without writing code. It supports the following
capabilities:

* Loading CSV datasets and selecting the categorical columns available for
  raking.
* Creating, editing, and deleting target distributions with automatic
  normalisation to 100%.
* Persisting target schemes as JSON files so that weighting configurations can
  be reloaded for future sessions.
* Selecting an existing weight column or defining a new output column name.
* Running the raking algorithm and reviewing a structured summary of the
  resulting weights and efficiency metrics.

## Getting started

1. Install the project dependencies (see `requirements.txt`). Ensure that a
   Python Tkinter runtime is available on your platform.
2. Execute the GUI with:

   ```bash
   python -m quantipy.gui.rake_gui
   ```

3. Load a CSV file, pick a column, enter the target percentages (they will be
   normalised automatically), and click **Save targets**.
4. Repeat the process for additional columns. The **Current targets** table can
   be used to edit or remove entries.
5. Provide the desired weight column name and click **Run weighting** to execute
   Quantipy's `Rake` engine. Review the output in the **Weighting summary** and
   **Activity log** panels.

For deployment, consider wrapping the GUI in a container that installs
`python3-tk` and uses `xvfb-run` so that the application can run in headless
settings.
