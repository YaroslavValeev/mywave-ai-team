# Server execution prerequisites

The patch executor requires git, GitHub CLI and pytest.
Use a separate clean checkout, not the production checkout.
Allow only that checkout through EXECUTION_ALLOWED_ROOTS_JSON.
Keep patches inside ARTIFACTS_DIR.
Owner approval binds the repository, base SHA and patch SHA256.
Changed inputs require fresh approval.
Execution must run tests before committing and creating a PR.
A created PR remains APPROVED_WAIT_MERGE until the owner acts.
Merge and deployment require their separate owner gates.
Release build_timestamp must describe the image build.
