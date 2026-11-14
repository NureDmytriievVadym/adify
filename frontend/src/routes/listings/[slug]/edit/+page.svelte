<script lang="ts">
  import { tick } from 'svelte';
  import { goto } from '$app/navigation';
  import type { PageData } from './$types';
  import Icon from '#lib/components/Icon.svelte';
  import ListingFields from '#lib/components/ListingFields.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { isVerified } from '#lib/accounts/verification.ts';
  import {
    MAX_ATTACHMENTS,
    deleteAttachment,
    fetchOwnListing,
    formatSize,
    inputFromListing,
    updateListing,
    uploadAttachment,
    validateFiles,
    validateListing,
    type ApiListing,
    type FieldErrors,
    type ListingField,
    type ListingInput,
    type OwnListingResult,
  } from '#lib/listings/api.ts';

  let { data }: { data: PageData } = $props();

  const order: ListingField[] = [
    'category',
    'title',
    'description',
    'expiry_date',
    'price',
    'delivery_days',
    'specs',
  ];

  let loaded = $state<OwnListingResult | null>(null);
  let listing = $state<ApiListing | null>(null);
  let input = $state<ListingInput | null>(null);
  let categoryLocked = $state(false);
  let removed = $state<string[]>([]);
  let files = $state<File[]>([]);
  let fileError = $state('');
  let errors = $state<FieldErrors>({});
  let message = $state('');
  let saving = $state(false);
  let failures = $state<string[] | null>(null);
  let form = $state<HTMLFormElement>();

  // A derived only changes when the id does, so a token refresh does not reload the form.
  const accountId = $derived(session.account?.id);

  $effect(() => {
    const id = data.listingId;
    if (!accountId) return;
    loaded = null;
    fetchOwnListing(id).then((result) => {
      if (data.listingId !== id) return;
      loaded = result;
      if (result.ok) start(result.listing);
    });
  });

  function start(source: ApiListing) {
    listing = source;
    input = inputFromListing(source);
    categoryLocked = source.locked_fields?.includes('category') ?? false;
    removed = [];
    files = [];
    errors = {};
    fileError = '';
    message = '';
    failures = null;
  }

  const isRequest = $derived(listing?.type === 'request');
  const expiryLocked = $derived(listing?.status === 'expired');
  const kept = $derived(listing?.attachments.filter((item) => !removed.includes(item.id)) ?? []);

  function attachmentError() {
    if (kept.length + files.length > MAX_ATTACHMENTS)
      return `A listing can have at most ${MAX_ATTACHMENTS} attachments. Remove a file first.`;
    return validateFiles(files) ?? '';
  }

  function pickFiles(event: Event) {
    const picker = event.currentTarget as HTMLInputElement;
    files = [...files, ...Array.from(picker.files ?? [])];
    picker.value = '';
    fileError = attachmentError();
  }

  function removeFile(index: number) {
    files = files.filter((_, position) => position !== index);
    fileError = attachmentError();
  }

  function toggleRemoved(id: string) {
    removed = removed.includes(id) ? removed.filter((item) => item !== id) : [...removed, id];
    fileError = attachmentError();
  }

  async function focusFirstError() {
    await tick();
    const field = order.find((name) => errors[name]);
    const target = field
      ? form?.querySelector<HTMLElement>(`[name="${field}"]:not(:disabled)`)
      : fileError
        ? form?.querySelector<HTMLElement>('[name="attachments"]')
        : form?.querySelector<HTMLElement>('.form-alert');
    target?.focus();
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!listing || !input) return;
    message = '';
    errors = validateListing(input, listing.type, { allowPastExpiry: expiryLocked });
    fileError = attachmentError();
    if (Object.keys(errors).length > 0 || fileError) return focusFirstError();

    saving = true;
    const result = await updateListing(listing.id, listing.type, input);
    if (!result.ok) {
      saving = false;
      if (result.type === 'category_locked') {
        // An order became active after the form was opened: keep the stored category.
        const { category, ...rest } = result.fieldErrors;
        errors = rest;
        message = category ?? result.message ?? '';
        categoryLocked = true;
        input.category = listing.category;
      } else {
        errors = result.fieldErrors;
        message = result.message ?? '';
      }
      return focusFirstError();
    }

    const problems: string[] = [];
    for (const attachment of listing.attachments.filter((item) => removed.includes(item.id))) {
      const outcome = await deleteAttachment(listing.id, attachment);
      if (!outcome.ok) problems.push(outcome.message);
    }
    for (const file of files) {
      const outcome = await uploadAttachment(listing.id, file);
      if (!outcome.ok) problems.push(outcome.message);
    }
    saving = false;
    if (problems.length === 0)
      return goto(`/listings/${listing.id}`, { state: { listingSaved: true } });
    failures = problems;
  }
</script>

<svelte:head
  ><title>{listing ? `Edit “${listing.title}”` : 'Edit listing'} — Adify</title></svelte:head
>

<div class="container page-content register-page">
  <nav class="breadcrumbs" aria-label="Breadcrumb">
    <a href="/listings/mine">My listings</a><Icon name="chevron" size={13} /><a
      href={`/listings/${data.listingId}`}>Listing</a
    ><Icon name="chevron" size={13} /><span aria-current="page">Edit</span>
  </nav>

  <div class="page-intro">
    <span class="eyebrow"
      >{listing ? (isRequest ? 'EDIT AD REQUEST' : 'EDIT AD OFFERING') : 'EDIT LISTING'}</span
    >
    <h1>Keep your listing<br /><span>up to date.</span></h1>
    <p>Your changes appear on the listing page as soon as you save them.</p>
  </div>

  {#if failures && listing}
    <section class="register-card" role="alert" aria-labelledby="partial-title">
      <h2 id="partial-title" class="account-title">Your changes are saved</h2>
      <p class="field-hint">Some files could not be updated:</p>
      <ul class="file-list">
        {#each failures as failure (failure)}<li class="field-error">{failure}</li>{/each}
      </ul>
      <a class="button button-dark register-submit" href={`/listings/${listing.id}`}
        >View your listing <Icon name="arrow" /></a
      >
    </section>
  {:else if !session.account && session.restored}
    <section class="register-card">
      <p class="field-hint">Sign in to edit your listing.</p>
      <a class="button button-dark register-submit" href="/sign-in">Sign in <Icon name="arrow" /></a
      >
    </section>
  {:else if session.account && (session.account.role === 'customer' || session.account.role === 'provider') && !isVerified(session.account)}
    <section class="register-card" role="alert">
      <h2 class="account-title">Verify your account first</h2>
      <p class="field-hint">
        Editing listings needs a verified email address and phone number, just like publishing them.
      </p>
      <a class="button button-dark register-submit" href="/account#verification"
        >Verify now <Icon name="arrow" /></a
      >
    </section>
  {:else if !session.account || !loaded}
    <p class="field-hint" role="status">Loading the listing…</p>
  {:else if !loaded.ok}
    <section class="register-card" role="alert">
      <h2 class="account-title">
        {loaded.reason === 'not_found'
          ? 'Listing not found'
          : loaded.reason === 'not_owner'
            ? 'This is not your listing'
            : 'Something went wrong'}
      </h2>
      <p class="field-hint">{loaded.message}</p>
      <a class="button button-dark register-submit" href="/listings/mine"
        >Go to my listings <Icon name="arrow" /></a
      >
    </section>
  {:else if listing && input}
    <form class="register-card" novalidate bind:this={form} onsubmit={submit}>
      {#if message}
        <p class="form-alert" role="alert" tabindex="-1">{message}</p>
      {/if}

      <ListingFields bind:input {errors} type={listing.type} {categoryLocked} {expiryLocked} />

      <fieldset class="filter-group attachment-editor">
        <legend>Attachments (optional)</legend>
        {#if listing.attachments.length}
          <ul class="file-list">
            {#each listing.attachments as attachment (attachment.id)}
              {@const removing = removed.includes(attachment.id)}
              <li class:removing>
                <span
                  >{attachment.filename} · {formatSize(attachment.size)}{removing
                    ? ' · will be removed'
                    : ''}</span
                >
                <button
                  class="text-button"
                  type="button"
                  aria-label={`${removing ? 'Keep' : 'Remove'} ${attachment.filename}`}
                  onclick={() => toggleRemoved(attachment.id)}
                  >{removing ? 'Keep' : 'Remove'}</button
                >
              </li>
            {/each}
          </ul>
        {/if}
        <label for="attachments">Add files</label>
        <input
          id="attachments"
          name="attachments"
          type="file"
          multiple
          accept=".jpg,.jpeg,.png,.gif,.webp,.mp4,.pdf"
          onchange={pickFiles}
          aria-invalid={fileError ? 'true' : undefined}
          aria-describedby={['attachments-hint', fileError && 'attachments-error']
            .filter(Boolean)
            .join(' ')}
        />
        <p class="field-hint" id="attachments-hint">
          Up to {MAX_ATTACHMENTS} files in total, 10 MB each: JPG, PNG, GIF, WebP, MP4, or PDF.
        </p>
        {#if files.length}
          <ul class="file-list">
            {#each files as file, index (file)}
              <li>
                <span>{file.name} · {formatSize(file.size)} · new</span>
                <button
                  class="text-button"
                  type="button"
                  aria-label={`Remove ${file.name}`}
                  onclick={() => removeFile(index)}>Remove</button
                >
              </li>
            {/each}
          </ul>
        {/if}
        {#if fileError}<p class="field-error" id="attachments-error">{fileError}</p>{/if}
      </fieldset>

      <div class="edit-actions">
        <button class="button button-dark" type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
          <Icon name="arrow" />
        </button>
        <a class="text-link" href={`/listings/${listing.id}`}>Cancel</a>
      </div>
    </form>
  {/if}
</div>
