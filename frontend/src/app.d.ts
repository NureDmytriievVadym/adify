declare global {
  namespace App {
    interface PageState {
      /** Set after the owner saves an edited listing (FR-017); not kept across reloads. */
      listingSaved?: boolean;
    }
  }
}

export {};
