<script lang="ts">
  import Icon from './Icon.svelte';
  import { formatSize } from '#lib/listings/api.ts';
  import {
    addEvidence,
    downloadEvidenceFile,
    formatMoment,
    type EvidenceFile,
    type Order,
  } from '#lib/orders/api.ts';

  // FR-041 (ADY-022): a note, files, or both. Every file is malware-scanned by the API.
  let { order, onchange }: { order: Order; onchange: (order: Order) => void } = $props();

  let note = $state('');
  let files: File[] = $state([]);
  let message: string | null = $state(null);
  let busy = $state(false);
  let fileInput: HTMLInputElement | undefined = $state();

  const MAX_FILES = 5;
  const MAX_BYTES = 10 * 1024 * 1024;
  const canAdd = $derived(order.status === 'in_progress' || order.status === 'in_review');

  function choose(event: Event) {
    const picker = event.currentTarget as HTMLInputElement;
    files = [...files, ...Array.from(picker.files ?? [])];
    picker.value = '';
    message = null;
  }

  function remove(index: number) {
    files = files.filter((_, position) => position !== index);
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    message = null;
    if (!note.trim() && files.length === 0) {
      message = 'Add a note or at least one file.';
      return;
    }
    if (files.length > MAX_FILES) {
      message = `Attach at most ${MAX_FILES} files.`;
      return;
    }
    if (files.some((file) => file.size > MAX_BYTES)) {
      message = 'Each evidence file can be at most 10 MB.';
      return;
    }
    busy = true;
    const result = await addEvidence(order.id, note, files);
    busy = false;
    if (!result.ok) {
      message = result.message;
      return;
    }
    note = '';
    files = [];
    if (fileInput) fileInput.value = '';
    onchange(result.value);
  }

  async function download(file: EvidenceFile) {
    const result = await downloadEvidenceFile(file);
    if (!result.ok) message = result.message;
  }
</script>

<h2 class="account-title">Evidence</h2>
<p class="field-hint">
  Notes and files from either participant. Every upload is scanned before it is stored.
</p>

{#if order.evidence.length === 0}
  <p class="field-hint">No evidence has been added yet.</p>
{:else}
  <ol class="evidence-list">
    {#each order.evidence as entry (entry.id)}
      <li class="evidence-item">
        <div class="evidence-meta">
          <strong>{entry.author.display_name}</strong>
          <span>{formatMoment(entry.created_at)}</span>
        </div>
        {#if entry.note}<p class="evidence-note">{entry.note}</p>{/if}
        {#if entry.files.length}
          <ul class="file-list evidence-files">
            {#each entry.files as file (file.id)}
              <li>
                <button type="button" class="text-button" onclick={() => download(file)}
                  >{file.filename}</button
                >
                <span>{formatSize(file.size)}</span>
              </li>
            {/each}
          </ul>
        {/if}
      </li>
    {/each}
  </ol>
{/if}

{#if canAdd}
  <form class="order-form evidence-form" novalidate onsubmit={submit}>
    {#if message}<p class="form-alert" role="alert">{message}</p>{/if}
    <div class="form-field">
      <label for="evidence-note">What does this evidence show? (optional)</label>
      <textarea
        id="evidence-note"
        rows="3"
        maxlength="2000"
        bind:value={note}
        aria-describedby="evidence-note-hint"></textarea>
      <p class="field-hint" id="evidence-note-hint">
        Up to 2,000 characters. Add files below if a note is not enough.
      </p>
    </div>
    <div class="form-field">
      <label for="evidence-files">Evidence files (optional)</label>
      <input
        id="evidence-files"
        name="evidence-files"
        type="file"
        multiple
        bind:this={fileInput}
        onchange={choose}
        aria-describedby="evidence-files-hint"
      />
      <p class="field-hint" id="evidence-files-hint">
        Up to {MAX_FILES} files of 10 MB each. Screenshots, screenshots of chats, PDFs, and other files
        are accepted; the malware scan rejects unsafe uploads.
      </p>
      {#if files.length}
        <ul class="file-list">
          {#each files as file, index (file.name + index)}
            <li>
              <span>{file.name} · {formatSize(file.size)}</span>
              <button
                type="button"
                class="text-button"
                aria-label={`Remove ${file.name}`}
                onclick={() => remove(index)}>Remove</button
              >
            </li>
          {/each}
        </ul>
      {/if}
    </div>
    <div class="order-form-actions">
      <button class="button button-dark" type="submit" disabled={busy}
        >{busy ? 'Uploading…' : 'Add evidence'} <Icon name="arrow" size={16} /></button
      >
    </div>
  </form>
{:else}
  {#if message}<p class="form-alert" role="alert">{message}</p>{/if}
  <p class="field-hint">Evidence can be added while the order is in progress or in review.</p>
{/if}
