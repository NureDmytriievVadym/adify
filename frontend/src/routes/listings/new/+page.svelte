<script lang="ts">
  import { tick } from 'svelte';
  import { goto } from '$app/navigation';
  import Icon from '#lib/components/Icon.svelte';
  import ListingFields from '#lib/components/ListingFields.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { isVerified } from '#lib/accounts/verification.ts';
  import {
    MAX_ATTACHMENTS,
    createListing,
    defaultExpiryDate,
    formatSize,
    uploadAttachment,
    validateFiles,
    validateListing,
    type FieldErrors,
    type ListingField,
    type ListingInput,
  } from '#lib/listings/api.ts';

  const order: ListingField[] = [
    'category',
    'title',
    'description',
    'expiry_date',
    'price',
    'delivery_days',
    'specs',
  ];

  const type = $derived(session.account?.role === 'customer' ? 'request' : 'offer');
  const isRequest = $derived(type === 'request');

  let input: ListingInput = $state({
    category: '',
    title: '',
    description: '',
    expiryDate: defaultExpiryDate(),
    price: '',
    delivery_days: '',
    specs: [{ label: '', value: '' }],
    ageMin: '',
    ageMax: '',
    country: '',
    socioeconomic: '',
    traits: '',
  });
  let files: File[] = $state([]);
  let fileError = $state('');
  let errors: FieldErrors = $state({});
  let message = $state('');
  let submitting = $state(false);
  let created: { id: string; failures: string[] } | null = $state(null);
  let form: HTMLFormElement | undefined = $state();

  function pickFiles(event: Event) {
    const picker = event.currentTarget as HTMLInputElement;
    files = [...files, ...Array.from(picker.files ?? [])];
    picker.value = '';
    fileError = validateFiles(files) ?? '';
  }

  const removeFile = (index: number) => {
    files = files.filter((_, position) => position !== index);
    fileError = validateFiles(files) ?? '';
  };

  async function focusFirstError() {
    await tick();
    const field = order.find((name) => errors[name]);
    const target = field
      ? form?.querySelector<HTMLElement>(`[name="${field}"]`)
      : fileError
        ? form?.querySelector<HTMLElement>('[name="attachments"]')
        : form?.querySelector<HTMLElement>('.form-alert');
    target?.focus();
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    message = '';
    errors = validateListing(input, type);
    fileError = validateFiles(files) ?? '';
    if (Object.keys(errors).length > 0 || fileError) return focusFirstError();

    submitting = true;
    const result = await createListing(type, input);
    if (!result.ok) {
      submitting = false;
      errors = result.fieldErrors;
      message = result.message ?? '';
      return focusFirstError();
    }
    const failures: string[] = [];
    for (const file of files) {
      const upload = await uploadAttachment(result.listing.id, file);
      if (!upload.ok) failures.push(upload.message);
    }
    submitting = false;
    if (failures.length === 0) return goto(`/listings/${result.listing.id}`);
    created = { id: result.listing.id, failures };
  }
</script>

<svelte:head
  ><title>{isRequest ? 'Create an ad request' : 'Create an ad offering'} — Adify</title><meta
    name="description"
    content="Publish an advertising listing on Adify, the internet advertising marketplace for Ukraine."
  /></svelte:head
>

<div class="container page-content register-page">
  <div class="page-intro">
    <span class="eyebrow">{isRequest ? 'NEW AD REQUEST' : 'NEW AD OFFERING'}</span>
    {#if session.account && isRequest}
      <h1>Tell providers<br /><span>what you need.</span></h1>
      <p>Describe the advertising you want to buy and your budget in UAH.</p>
    {:else if session.account}
      <h1>Show customers<br /><span>what you offer.</span></h1>
      <p>Describe your advertising placement, its price in UAH, and how fast you deliver.</p>
    {:else}
      <h1>Create a<br /><span>listing.</span></h1>
    {/if}
  </div>

  {#if created}
    <section class="register-card" role="alert" aria-labelledby="partial-title">
      <h2 id="partial-title" class="account-title">Your listing is published</h2>
      <p class="field-hint">Some files could not be attached:</p>
      <ul class="file-list">
        {#each created.failures as failure (failure)}<li class="field-error">{failure}</li>{/each}
      </ul>
      <a class="button button-dark register-submit" href={`/listings/${created.id}`}
        >View your listing <Icon name="arrow" /></a
      >
    </section>
  {:else if session.account && (session.account.role === 'customer' || session.account.role === 'provider') && !isVerified(session.account)}
    <section class="register-card" role="alert">
      <h2 class="account-title">Verify your account first</h2>
      <p class="field-hint">
        Creating listings needs a verified email address and phone number, so other users know they
        are dealing with a real person.
      </p>
      <a class="button button-dark register-submit" href="/account#verification"
        >Verify now <Icon name="arrow" /></a
      >
    </section>
  {:else if session.account && (session.account.role === 'customer' || session.account.role === 'provider')}
    <form class="register-card" novalidate bind:this={form} onsubmit={submit}>
      {#if message}
        <p class="form-alert" role="alert" tabindex="-1">{message}</p>
      {/if}

      <ListingFields bind:input {errors} {type} />

      <div class="form-field">
        <label for="attachments">Attachments (optional)</label>
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
          Up to {MAX_ATTACHMENTS} files of 10 MB each: JPG, PNG, GIF, WebP, MP4, or PDF.
        </p>
        {#if files.length}
          <ul class="file-list">
            {#each files as file, index (file)}
              <li>
                <span>{file.name} · {formatSize(file.size)}</span>
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
      </div>

      <button class="button button-dark register-submit" type="submit" disabled={submitting}>
        {submitting ? 'Publishing…' : isRequest ? 'Publish request' : 'Publish offering'}
        <Icon name="arrow" />
      </button>
    </form>
  {:else if session.account}
    <section class="register-card">
      <p class="field-hint">Only customers and providers can create listings.</p>
    </section>
  {:else if session.restored}
    <section class="register-card">
      <p class="field-hint">Sign in to create a listing.</p>
      <a class="button button-dark register-submit" href="/sign-in">Sign in <Icon name="arrow" /></a
      >
    </section>
  {:else}
    <p class="field-hint" role="status">Loading…</p>
  {/if}
</div>
