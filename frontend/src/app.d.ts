declare global {
  namespace App {
    interface PageState {
      /** Set after the owner saves an edited listing (FR-017); not kept across reloads. */
      listingSaved?: boolean;
      /** Set after the owner deletes a listing (FR-020): how the API handled it. */
      listingDeleted?: 'removed' | 'soft_deleted';
    }
  }
}

export {};
