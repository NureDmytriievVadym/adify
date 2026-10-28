<script lang="ts">
  import type { PageData } from './$types';
  import { getCategory, formatUah } from '#lib/demo/marketplace.ts';
  import ListingArtwork from '#lib/components/ListingArtwork.svelte';
  import PreviewNotice from '#lib/components/PreviewNotice.svelte';
  import Icon from '#lib/components/Icon.svelte';
  let { data }: { data: PageData } = $props();
  const listing = $derived(data.listing);
</script>

<svelte:head
  ><title>{listing.title} — Adify</title><meta
    name="description"
    content={`Sample ${getCategory(listing.categoryId).name.toLowerCase()} listing. ${listing.title}. Explore the Adify website preview.`}
  /></svelte:head
>

<div class="container page-content">
  <nav class="breadcrumbs" aria-label="Breadcrumb">
    <a href="/">Home</a><Icon name="chevron" size={13} /><a href="/listings">Marketplace</a><Icon
      name="chevron"
      size={13}
    /><span aria-current="page">Sample listing</span>
  </nav>
  <PreviewNotice />
  <div class="detail-layout">
    <div class="detail-main">
      <div class="detail-title">
        <span class="eyebrow"
          >{getCategory(listing.categoryId).name} · {listing.type === 'offer'
            ? 'Advertising offer'
            : 'Ad request'}</span
        >
        <h1>{listing.title}</h1>
      </div>
      <ListingArtwork category={listing.categoryId} large />
      <section class="detail-section">
        <h2>About this {listing.type === 'offer' ? 'placement' : 'request'}</h2>
        <p>{listing.description}</p>
      </section>
      <section class="detail-section">
        <h2>Placement specification</h2>
        {#if listing.placement.length}<p class="muted">
            The technical requirements for this example placement.
          </p>
          <dl class="specification-list">
            {#each listing.placement as spec (spec.label)}<div>
                <dt>{spec.label}</dt>
                <dd>{spec.value}</dd>
              </div>{/each}
          </dl>{:else}<p>No technical requirements specified by the customer.</p>{/if}
      </section>
    </div>
    <aside class="detail-sidebar">
      <div class="provider-card">
        <div class="provider-heading">
          <span class="avatar avatar-large">{listing.initials}</span>
          <div>
            <strong>{listing.owner}</strong><span
              >{listing.type === 'offer' ? 'Provider' : 'Customer'} · Sample profile</span
            >
          </div>
        </div>
        <div class="detail-price">
          <span>{listing.type === 'offer' ? 'Placement price' : 'Request budget'}</span><strong
            >{formatUah(listing.price)}</strong
          >
        </div>
        <div class="delivery-info">
          <Icon name="clock" size={18} /><span>Estimated delivery: {listing.delivery}</span>
        </div>
        <div class="preview-actions" aria-describedby="contact-note">
          <button class="button button-dark" type="button" disabled
            >Start chat <Icon name="social" size={18} /></button
          ><button class="button button-outline" type="button" disabled>Reveal phone number</button>
        </div>
        <p id="contact-note" class="small-note">
          Contact actions are unavailable in this preview. In the marketplace, they require a
          signed-in account with verified email and phone.
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
</div>
