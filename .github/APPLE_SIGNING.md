# FreeMoCap Apple signing credentials

The installer workflow uses a certificate to sign the app and an Apple account
with an app-specific password to notarize it. These are separate credentials.
The canonical GitHub password secret is `APPLE_FREEMOCAP_APP_SPECIFIC_PASSWORD`.
The workflow passes its value as Electron's `APPLE_APP_SPECIFIC_PASSWORD`.

## Secret map

| GitHub Actions secret | Value | Where to obtain it |
| --- | --- | --- |
| `APPLE_ID` | Apple account email used for notarization | The Apple account that belongs to the intended developer team |
| `APPLE_FREEMOCAP_APP_SPECIFIC_PASSWORD` | App-specific password generated for FreeMoCap | Apple Account > Sign-In and Security > App-Specific Passwords |
| `APPLE_TEAM_ID` | Developer membership's 10-character Team ID | Apple Developer account > Membership details |
| `MAC_CERTIFICATE_P12` | Base64-encoded Developer ID Application signing identity, including its private key | Export the signing identity from the Mac holding its private key, then encode the `.p12` file |
| `MAC_CERTIFICATE_PASSWORD` | Password chosen when exporting that `.p12` | The person who exported the signing identity |

`APPLE_ID` is not a bundle ID, numeric App Store app ID, or password. The
app-specific password is not your normal Apple account password or an App Store
Connect API key. The certificate password unlocks the exported file; it is not
either Apple account password. Apple documents app-specific passwords, Team IDs,
Developer ID certificates, and exported identities separately
[@appleAppSpecificPasswords; @appleTeamId; @appleDeveloperId; @appleSigningIdentity].

## Organization versus repository secrets

Recommended setup: retain the existing Apple organization secrets and add the
FreeMoCap-specific password there, with **Selected repositories** access that
includes `freemocap/freemocap`. Avoid duplicate repository secrets with the same
names. Organization secrets are supplied automatically when access is granted;
there is no copy or explicit handoff in the workflow. A private-repositories-only
policy does not cover this public repository. [@githubActionsSecrets]

A repository secret overrides an organization secret with the same name. This
workflow does not select a GitHub environment, so environment secrets are not
part of its configuration. A repository-only password is also valid if you want
to manage it in FreeMoCap's settings; choose one location for that name.
[@githubSecretPrecedence]

## Restore the password

1. Sign in at [Apple Account](https://account.apple.com) as the account used for
   `APPLE_ID`. Two-factor authentication must be enabled.
2. Open **Sign-In and Security > App-Specific Passwords** and generate a password.
   Use the label **FreeMoCap GitHub Actions**. Copy the generated password, not
   the label. Changing or resetting the primary Apple account password revokes
   existing app-specific passwords. [@appleAppSpecificPasswords]
3. Open [FreeMoCap organization Actions secrets](https://github.com/organizations/freemocap/settings/secrets/actions).
   Create or update `APPLE_FREEMOCAP_APP_SPECIFIC_PASSWORD` with that value.
   Set **Repository access** to **Selected repositories** and include
   `freemocap/freemocap`. Preserve any existing access for other secrets.
   Alternatively, create this secret in
   [FreeMoCap repository Actions secrets](https://github.com/freemocap/freemocap/settings/secrets/actions).
   Paste the password directly into GitHub, not chat, source files, or logs.
   [@githubActionsSecrets]
4. Check that `APPLE_ID` is the email for the account you just used. GitHub cannot
   display an existing secret's value. If its value is uncertain, establish the
   correct account and re-enter the email. Check other consumers before changing
   a shared organization secret; a repository override can isolate a correction.
5. At [Apple Developer](https://developer.apple.com/account), select the intended
   membership and open **Membership details**. Confirm `APPLE_TEAM_ID` against
   its Team ID. [@appleTeamId]
6. Keep the certificate secrets unless signing shows a separate problem. Their
   presence does not prove that the certificate is valid or unexpired. If repair
   is needed, review **Certificates, Identifiers & Profiles > Certificates** for
   the Developer ID Application certificate. A downloaded `.cer` alone does not
   supply the private key: export the signing identity as a password-protected
   `.p12` from the Mac holding it. Encode that file for `MAC_CERTIFICATE_P12` and
   save its export password as `MAC_CERTIFICATE_PASSWORD`.
   [@appleDeveloperId; @appleSigningIdentity]

## Migration and verification

Older revisions use `APPLE_ID_PASSWORD`; some development revisions use
`APPLE_APP_SPECIFIC_PASSWORD` as the GitHub secret name. This branch uses only
`APPLE_FREEMOCAP_APP_SPECIFIC_PASSWORD`, with no fallback to ambiguous names.
Do not delete or rename shared secrets until their other consumers are checked.

After saving the secret, run the credential check on a published branch containing
this workflow:

```shell
gh workflow run build-installers-pyinstaller.yml --repo freemocap/freemocap --ref fix/apple-signing-credentials -f check_apple_credentials=true
```

The macOS job calls Apple's notary service to read submission history and
discards the response. Success verifies the account email, team ID and
app-specific password together [@appleNotaryCredentialTest]. The installer
build and release jobs are skipped. A full installer build separately verifies
the certificate and an actual submission.

For a read-only inventory of names available to this repository:

```shell
gh secret list --repo freemocap/freemocap
gh api --paginate repos/freemocap/freemocap/actions/organization-secrets --jq '.secrets[].name'
```

The second command lists organization secrets granted to this repository even
when the CLI lacks permission to list the entire organization's secret inventory.
Neither command reveals values.

Audit on 2026-11-03: the four existing Apple account/team/certificate secrets were
available through the organization; neither legacy password name nor the new
FreeMoCap-specific name was available. The only repository secrets were
`PYPI_TOKEN` and `SKELLYPINGS_SECRET`. The October 27 run
[`40555847177`](https://github.com/freemocap/freemocap/actions/runs/40555847177)
failed because `APPLE_ID_PASSWORD` was absent. Values and organization secrets
not granted to this repository could not be inspected.

Sources are registered in `references.bib`. Validate citations from the repository
root with `python -B tools/check_references.py` and
`python -B -m unittest discover -s tools -p "test_references.py" -v`.
