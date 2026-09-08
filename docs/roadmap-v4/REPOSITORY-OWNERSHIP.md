# Repository ownership

| Concern | Owner |
| --- | --- |
| Public facade, ProjectSpec validation, manifests, composition, generated content and render validation | forge-template |
| Generic UX, ProjectSpec construction, configuration, diagnostics and errors | create-forge |
| Staging, lock resolution, filesystem application, Git and hook execution | create-forge |
| Provider package review/publication and generated-project resource audits | forge-template |
| Adoption and installed-console validation against published provider artefacts | create-forge |
| Shared user guide | create-forge; link provider details rather than duplicate them |
| Contract acceptance and coordinated release evidence | Both, through repository-owned children |

Generated projects and independent downstream clients gain no dependency on
create-forge. Generated projects gain no Forge runtime package dependency.
Foundation remains domain-neutral; archetypes do not read sibling resources.

Each issue has one repository, one stage and one parent epic. Only repositories
with unfinished work in a stage receive an epic and milestone. Cross-repository
blockers are native issue dependencies when filed, not duplicate child issues.
