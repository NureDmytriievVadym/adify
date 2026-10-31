<script lang="ts">
  import { PUBLIC_API_BASE_URL } from '$app/env/public';
  import type { PageData } from './$types';
  import { getCategory, formatUah } from '#lib/demo/marketplace.ts';
  import {
    fetchListing,
    formatDelivery,
    formatSize,
    type Attachment,
    type FetchResult,
    type ListingType,
    type Spec,
  } from '#lib/listings/api.ts';
  import ListingArtwork from '#lib/components/ListingArtwork.svelte';
  import PreviewNotice from '#lib/components/PreviewNotice.svelte';
  import Icon from '#lib/components/Icon.svelte';

  let { data }: { data: PageData } = $props();

  interface View {
    sample: boolean;
    categoryId: string;
    type: ListingType;
    title: string;
    description: string;
    owner: string;
    ownerRole: string;
    price: number;
    delivery: string;
    placement: Spec[];
    attachments: Attachment[];
  }

  let live: FetchResult | null = $state(null);

  $effect(() => {
    const id = data.listingId;
    if (!id) return;
    live = null;
    fetchListing(id).then((result) => {
      if (data.listingId === id) live = result;
    });
  });

  const initials = (name: string) =>
    name
      .split(/\s+/)
      .map((word) => word[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();

  const view: View | null = $derived.by(() => {
    if (data.demo) {
      const { categoryId, type, title, description, owner, price, delivery, placement } = data.demo;
      return {
        sample: true,
        categoryId,
        type,
        title,
        description,
        owner,
        ownerRole: `${type === 'offer' ? 'Provider' : 'Customer'} · Sample profile`,
        price,
        delivery,
        placement,
        attachments: [],
      };
    }
    if (!live?.ok) return null;
    const { listing } = live;
    return {
      sample: false,
      categoryId: listing.category,
      type: listing.type,
      title: listing.title,
      description: listing.description,
      owner: listing.owner.display_name,
      ownerRole: listing.owner.role === 'provider' ? 'Provider' : 'Customer',
      price: Number(listing.price_uah),
      delivery: formatDelivery(listing.delivery_days),
      placement: listing.specs,
      attachments: listing.attachments,
    };
  });

  const attachmentUrl = (attachment: Attachment) => `${PUBLIC_API_BASE_URL}${attachment.url}`;
</script>

<svelte:head
  ><title>{view ? `${view.title} — Adify` : 'Listing — Adify'}</title>
  {#if view?.sample}<meta
      name="description"
      content={`Sample ${getCategory(view.categoryId).name.toLowerCase()} listing. ${view.title}. Explore the Adify website preview.`}
    />{/if}</svelte:head
>

<div class="container page-content">
  <nav class="breadcrumbs" aria-label="Breadcrumb">
    <a href="/">Home</a><Icon name="chevron" size={13} /><a href="/listings">Marketplace</a><Icon
      name="chevron"
      size={13}
    /><span aria-current="page">{view?.sample === false ? 'Listing' : 'Sample listing'}</span>
  </nav>
  {#if view}
    {#if view.sample}<PreviewNotice />{/if}
    <div class="detail-layout">
      <div class="detail-main">
        <div class="detail-title">
          <span class="eyebrow"
            >{getCategory(view.categoryId).name} · {view.type === 'offer'
              ? 'Advertising offer'
              : 'Ad request'}</span
          >
          <h1>{view.title}</h1>
        </div>
        <ListingArtwork category={view.categoryId} large />
        <section class="detail-section">
          <h2>About this {view.type === 'offer' ? 'placement' : 'request'}</h2>
          <p>{view.description}</p>
        </section>
        <section class="detail-section">
          <h2>Placement specification</h2>
          {#if view.placement.length}<p class="muted">
              The technical requirements for this {view.sample ? 'example placement' : 'listing'}.
            </p>
            <dl class="specification-list">
              {#each view.placement as spec (spec.label)}<div>
                  <dt>{spec.label}</dt>
                  <dd>{spec.value}</dd>
                </div>{/each}
            </dl>{:else}<p>
              {view.type === 'offer'
                ? 'No technical requirements specified by the provider.'
                : 'No technical requirements specified by the customer.'}
            </p>{/if}
        </section>
        {#if view.attachments.length}
          <section class="detail-section">
            <h2>Attachments</h2>
            <ul class="attachment-grid">
              {#each view.attachments as attachment (attachment.id)}
                <li>
                  <a href={attachmentUrl(attachment)} target="_blank" rel="noopener noreferrer">
                    {#if attachment.content_type.startsWith('image/')}
                      <img src={attachmentUrl(attachment)} alt="" loading="lazy" />
                    {:else}
                      <span class="attachment-file" aria-hidden="true"
                        >{attachment.content_type === 'application/pdf' ? 'PDF' : 'MP4'}</span
                      >
                    {/if}
                    {attachment.filename}
                    <span>{formatSize(attachment.size)}</span>
                  </a>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      </div>
      <aside class="detail-sidebar">
        <div class="provider-card">
          <div class="provider-heading">
            <span class="avatar avatar-large">{initials(view.owner)}</span>
            <div>
              <strong>{view.owner}</strong><span>{view.ownerRole}</span>
            </div>
          </div>
          <div class="detail-price">
            <span>{view.type === 'offer' ? 'Placement price' : 'Request budget'}</span><strong
              >{formatUah(view.price)}</strong
            >
          </div>
          <div class="delivery-info">
            <Icon name="clock" size={18} /><span>Estimated delivery: {view.delivery}</span>
          </div>
          <div class="preview-actions" aria-describedby="contact-note">
            <button class="button button-dark" type="button" disabled
              >Start chat <Icon name="social" size={18} /></button
            ><button class="button button-outline" type="button" disabled
              >Reveal phone number</button
            >
          </div>
          <p id="contact-note" class="small-note">
            {view.sample
              ? 'Contact actions are unavailable in this preview. In the marketplace, they require a signed-in account with verified email and phone.'
              : 'Chat and phone numbers are coming in a later release. They will require a signed-in account with verified email and phone.'}
          </p>
        </div>
        <div class="sidebar-note">
          <Icon name="shield" size={22} />
          <p>
            <strong>Clear requirements. Shared expectations.</strong><br />Review the placement
            specification before agreeing on an order.
          </p>
        </div>
        <a class="text-link" href="/orders/demo"
          >View an example order <Icon name="arrow" size={17} /></a
        >
      </aside>
    </div>
  {:else if live && !live.ok}
    <div class="page-intro">
      <h1>{live.notFound ? 'Listing not found.' : 'Something went wrong.'}</h1>
      <p role="alert">{live.message}</p>
      <a class="button button-dark" href="/listings">Back to the marketplace</a>
    </div>
  {:else}
    <p class="field-hint" role="status">Loading the listing…</p>
  {/if}
</div>
