<script lang="ts">
  import Icon from './Icon.svelte';
  import { categories, categoryName } from '#lib/listings/catalog.ts';
  import {
    MAX_SPECS,
    type FieldErrors,
    type ListingField,
    type ListingInput,
    type ListingType,
  } from '#lib/listings/api.ts';

  // Shared by the create and edit forms so both keep the same labels, limits, and hints.
  let {
    input = $bindable(),
    errors,
    type,
    categoryLocked = false,
  }: {
    input: ListingInput;
    errors: FieldErrors;
    type: ListingType;
    /** FR-017: an active order fixes the category; the select stays visible but disabled. */
    categoryLocked?: boolean;
  } = $props();

  const isRequest = $derived(type === 'request');

  const describedBy = (field: ListingField, ...extra: (string | false)[]) =>
    [...extra, errors[field] && `${field}-error`].filter(Boolean).join(' ') || undefined;
</script>

<div class="form-field">
  <label for="category">Category</label>
  <select
    id="category"
    name="category"
    bind:value={input.category}
    disabled={categoryLocked}
    aria-invalid={errors.category ? 'true' : undefined}
    aria-describedby={describedBy('category', categoryLocked && 'category-locked')}
  >
    <option value="">Choose a category</option>
    {#each categories as category (category.id)}
      <option value={category.id}>{category.name}</option>
    {/each}
  </select>
  {#if categoryLocked}
    <p class="field-hint locked-hint" id="category-locked">
      <Icon name="shield" size={15} />
      <span
        >This listing has an active order, so it stays in {categoryName(input.category)}. You can
        still change every other detail.</span
      >
    </p>
  {/if}
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
    aria-describedby={describedBy('description', 'description-hint')}></textarea>
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

<fieldset class="filter-group audience-editor">
  <legend>Target audience (optional)</legend>
  <p class="field-hint">
    Who should see this advertising? Leave any field empty when the audience is open.
  </p>
  <div class="filter-pair">
    <div>
      <label for="age_min">Age from</label>
      <input
        id="age_min"
        name="age_min"
        inputmode="numeric"
        placeholder="18"
        bind:value={input.ageMin}
        aria-invalid={errors.audience ? 'true' : undefined}
      />
    </div>
    <div>
      <label for="age_max">Age to</label>
      <input
        id="age_max"
        name="age_max"
        inputmode="numeric"
        placeholder="34"
        bind:value={input.ageMax}
        aria-invalid={errors.audience ? 'true' : undefined}
      />
    </div>
  </div>
  <label for="audience_country">Country</label>
  <input
    id="audience_country"
    name="audience_country"
    maxlength="100"
    placeholder="Ukraine"
    bind:value={input.country}
  />
  <label for="audience_socioeconomic">Socioeconomic background</label>
  <input
    id="audience_socioeconomic"
    name="audience_socioeconomic"
    maxlength="100"
    placeholder="Middle income"
    bind:value={input.socioeconomic}
  />
  <label for="audience_traits">Traits</label>
  <input
    id="audience_traits"
    name="audience_traits"
    maxlength="300"
    placeholder="Gamers, students"
    bind:value={input.traits}
    aria-describedby="audience_traits-hint"
  />
  <p class="field-hint" id="audience_traits-hint">Separate traits with commas.</p>
  {#if errors.audience}<p class="field-error" id="audience-error">{errors.audience}</p>{/if}
</fieldset>

<fieldset
  class="spec-editor"
  name="specs"
  tabindex="-1"
  aria-describedby={describedBy('specs', 'specs-hint')}
>
  <legend>{isRequest ? 'Requirements (optional)' : 'Placement specification (optional)'}</legend>
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
        onclick={() => (input.specs = input.specs.filter((_, position) => position !== index))}
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
