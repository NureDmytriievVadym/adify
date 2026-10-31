<script lang="ts">
  import { tick } from 'svelte';
  import { goto } from '$app/navigation';
  import Icon from '#lib/components/Icon.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { categories } from '#lib/demo/marketplace.ts';
  import {
    MAX_ATTACHMENTS,
    MAX_SPECS,
    createListing,
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
    price: '',
    delivery_days: '',
    specs: [{ label: '', value: '' }],
  });
  let files: File[] = $state([]);
  let fileError = $state('');
  let errors: FieldErrors = $state({});
  let message = $state('');
  let submitting = $state(false);
  let created: { id: string; failures: string[] } | null = $state(null);
  let form: HTMLFormElement | undefined = $state();

  const describedBy = (field: ListingField, hint = false) =>
    [hint && `${field}-hint`, errors[field] && `${field}-error`].filter(Boolean).join(' ') ||
    undefined;

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
  {:else if session.account && (session.account.role === 'customer' || session.account.role === 'provider')}
    <form class="register-card" novalidate bind:this={form} onsubmit={submit}>
      {#if message}
        <p class="form-alert" role="alert" tabindex="-1">{message}</p>
      {/if}

      <div class="form-field">
        <label for="category">Category</label>
        <select
          id="category"
          name="category"
          bind:value={input.category}
          aria-invalid={errors.category ? 'true' : undefined}
          aria-describedby={describedBy('category')}
        >
          <option value="">Choose a category</option>
          {#each categories as category (category.id)}
            <option value={category.id}>{category.name}</option>
          {/each}
        </select>
        {#if errors.category}<p class="field-error" id="category-error">{errors.category}</p>{/if}
      </div>

      <div class="form-field">
        <label for="title">Title</label>
        <input
          id="title"
          name="title"
          maxlength="120"
          bind:value={input.title}
          aria-invalid={errors.title ? 'true' : undefined}
          aria-describedby={describedBy('title')}
        />
        {#if errors.title}<p class="field-error" id="title-error">{errors.title}</p>{/if}
      </div>

      <div class="form-field">
        <label for="description">Description</label>
        <textarea
          id="description"
          name="description"
          maxlength="5000"
          bind:value={input.description}
          aria-invalid={errors.description ? 'true' : undefined}
          aria-describedby={describedBy('description', true)}></textarea>
        <p class="field-hint" id="description-hint">
          {isRequest
            ? 'What do you advertise, and what are you looking for?'
            : 'What does the placement include, and where will it appear?'}
        </p>
        {#if errors.description}
          <p class="field-error" id="description-error">{errors.description}</p>
        {/if}
      </div>

      <div class="form-field">
        <label for="price">{isRequest ? 'Budget (UAH)' : 'Price (UAH)'}</label>
        <input
          id="price"
          name="price"
          inputmode="decimal"
          placeholder="2500"
          bind:value={input.price}
          aria-invalid={errors.price ? 'true' : undefined}
          aria-describedby={describedBy('price')}
        />
        {#if errors.price}<p class="field-error" id="price-error">{errors.price}</p>{/if}
      </div>

      <div class="form-field">
        <label for="delivery_days"
          >{isRequest ? 'Desired delivery time in days (optional)' : 'Delivery time in days'}</label
        >
        <input
          id="delivery_days"
          name="delivery_days"
          inputmode="numeric"
          placeholder="5"
          bind:value={input.delivery_days}
          aria-invalid={errors.delivery_days ? 'true' : undefined}
          aria-describedby={describedBy('delivery_days')}
        />
        {#if errors.delivery_days}
          <p class="field-error" id="delivery_days-error">{errors.delivery_days}</p>
        {/if}
      </div>

      <fieldset
        class="spec-editor"
        name="specs"
        tabindex="-1"
        aria-describedby={describedBy('specs', true)}
      >
        <legend
          >{isRequest ? 'Requirements (optional)' : 'Placement specification (optional)'}</legend
        >
        <p class="field-hint" id="specs-hint">
          {isRequest
            ? 'Technical requirements, for example “Length: 1,000 words”.'
            : 'Formats and limits, for example “Dimensions: 728 × 90 px”.'}
        </p>
        {#each input.specs as spec, index (index)}
          <div class="spec-row">
            <input
              aria-label={`Specification ${index + 1} name`}
              placeholder="Name"
              maxlength="60"
              bind:value={spec.label}
            />
            <input
              aria-label={`Specification ${index + 1} value`}
              placeholder="Value"
              maxlength="300"
              bind:value={spec.value}
            />
            <button
              class="button button-outline button-small"
              type="button"
              aria-label={`Remove specification ${index + 1}`}
              onclick={() =>
                (input.specs = input.specs.filter((_, position) => position !== index))}
              ><Icon name="close" size={16} /></button
            >
          </div>
        {/each}
        {#if input.specs.length < MAX_SPECS}
          <button
            class="button button-outline button-small spec-add"
            type="button"
            onclick={() => (input.specs = [...input.specs, { label: '', value: '' }])}
            >Add a specification</button
          >
        {/if}
        {#if errors.specs}<p class="field-error" id="specs-error">{errors.specs}</p>{/if}
      </fieldset>

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
