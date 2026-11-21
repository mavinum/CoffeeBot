# Third-Party Notices

CoffeeBot depends on the third-party runtime packages listed below. This inventory reflects the direct dependencies declared in `pyproject.toml`, plus the Qt components installed with PyQt6. The dependency ranges can resolve to newer releases; check the metadata and license files for the exact versions included in each release.

Development and CI dependencies are not included in this runtime inventory. The transitive dependencies of the packages below are installed separately by the package installer and may vary by platform and resolved versions. Each installed distribution carries its own metadata and applicable notices. Before redistributing a frozen or otherwise bundled application, audit the exact build environment and include the license texts, copyright notices, and attributions required for every component shipped.

## Qt and PyQt6

- **PyQt6** — `GPL-3.0-only` (or available separately under Riverbank's commercial terms). [Upstream](https://www.riverbankcomputing.com/software/pyqt/).
- **Qt libraries (`PyQt6-Qt6`)** — the installed package declares `LGPL-3.0`; Qt modules and bundled third-party components may carry additional terms and notices. Check the license and notice files shipped with the exact Qt package and modules. [Qt licensing](https://www.qt.io/licensing/).
- **PyQt6-sip** — `BSD-2-Clause`. [Upstream](https://github.com/Python-SIP/sip).

If you distribute a bundled application, include the applicable PyQt, Qt, SIP, and Qt third-party license texts and notices for the components actually shipped. Follow the applicable license terms for the form of distribution. A normal CoffeeBot wheel declares PyQt6 as a dependency rather than bundling the Qt libraries itself.

## Python Runtime Dependencies

| Package | License | Upstream |
| --- | --- | --- |
| bcrypt | `Apache-2.0` | [pyca/bcrypt](https://github.com/pyca/bcrypt) |
| filelock | `MIT` | [tox-dev/py-filelock](https://github.com/tox-dev/py-filelock) |
| keyring | `MIT` | [jaraco/keyring](https://github.com/jaraco/keyring) |
| loguru | `MIT` | [Delgan/loguru](https://github.com/Delgan/loguru) |
| numpy | `BSD-3-Clause`, `0BSD`, `MIT`, `Zlib`, and `CC0-1.0` components | [numpy](https://github.com/numpy/numpy) |
| openpyxl | `MIT` | [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) |
| packaging | `Apache-2.0 OR BSD-2-Clause` | [pypa/packaging](https://github.com/pypa/packaging) |
| platformdirs | `MIT` | [tox-dev/platformdirs](https://github.com/tox-dev/platformdirs) |
| pyisemail | `MIT` | [michaelherold/pyIsEmail](https://github.com/michaelherold/pyIsEmail) |
| PyQt6 | `GPL-3.0-only` | [Riverbank Computing](https://www.riverbankcomputing.com/software/pyqt/) |
| secretstorage | `BSD-3-Clause` | [mitya57/secretstorage](https://github.com/mitya57/secretstorage) |
| webdav4 | `MIT` | [skshetry/webdav4](https://github.com/skshetry/webdav4) |

License identifiers above are based on upstream package metadata and license files. Copyright holders and the full license terms are identified in the upstream distributions; preserve those notices when copying or redistributing their code. In particular, NumPy and Qt distributions may include additional license and attribution files beyond the summary identifiers shown here.

If the license metadata or notice bundled with a specific release differs from this summary, the terms and notices shipped with that release control. This file is a summary, not a replacement for the component license texts.
