<div class="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 h-[calc(100vh-5rem)]">
    {{-- ===== Katalog produk (kiri) ===== --}}
    <div class="lg:col-span-8 flex flex-col h-full gap-4">
        <div class="flex gap-3">
            <input
                type="search"
                wire:model.live.debounce.300ms="search"
                placeholder="Cari nama, SKU, atau merek ban/oli/jasa…"
                class="flex-1 rounded-lg border-slate-300 dark:border-slate-700 dark:bg-slate-900"
            />
            <div class="flex rounded-lg overflow-hidden border border-slate-300 dark:border-slate-700">
                @foreach (['semua' => 'Semua', 'barang' => 'Ban & Sparepart', 'jasa' => 'Jasa Servis'] as $key => $label)
                    <button wire:click="$set('typeFilter', '{{ $key }}')"
                            class="px-4 text-sm {{ $typeFilter === $key ? 'bg-amber-500 text-black font-semibold' : 'bg-white dark:bg-slate-900' }}">
                        {{ $label }}
                    </button>
                @endforeach
            </div>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3 overflow-y-auto">
            @foreach ($this->products as $product)
                <button wire:click="addToCart({{ $product->id }})"
                        @disabled($product->type === 'barang' && $product->stock < 1)
                        class="text-left rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 hover:border-amber-500 transition">
                    <div class="flex justify-between items-start">
                        <span class="text-[11px] uppercase tracking-wider text-slate-500">{{ $product->sku }}</span>
                        <span class="text-[11px] rounded-md px-2 py-0.5 font-semibold
                            {{ $product->type === 'jasa' ? 'bg-sky-500/15 text-sky-600' : 'bg-amber-500/15 text-amber-600' }}">
                            {{ $product->type === 'jasa' ? 'Jasa' : 'Barang' }}
                        </span>
                    </div>
                    <div class="mt-2 font-semibold leading-snug">{{ $product->name }}</div>
                    <div class="text-xs text-slate-500">{{ $product->brand }} {{ $product->size }}</div>
                    <div class="mt-3 flex justify-between items-center">
                        <span class="font-mono font-bold text-amber-600">Rp {{ number_format($product->selling_price, 0, ',', '.') }}</span>
                        @if ($product->type === 'barang')
                            <span class="text-xs {{ $product->stock <= 4 ? 'text-red-500 font-semibold' : 'text-slate-500' }}">
                                Stok {{ $product->stock }}
                            </span>
                        @endif
                    </div>
                </button>
            @endforeach
        </div>
    </div>

    {{-- ===== Keranjang + checkout (kanan) ===== --}}
    <div class="lg:col-span-4 flex flex-col h-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div class="p-4 border-b border-slate-200 dark:border-slate-800 font-bold">Keranjang ({{ count($cart) }} item)</div>

        <div class="flex-1 overflow-y-auto divide-y divide-slate-200 dark:divide-slate-800">
            @foreach ($this->cartLines as $line)
                <div class="p-4 flex items-center gap-3">
                    <div class="flex-1">
                        <div class="text-sm font-semibold leading-snug">{{ $line['product']->name }}</div>
                        <div class="text-xs text-slate-500 font-mono">
                            Rp {{ number_format($line['product']->selling_price, 0, ',', '.') }} × {{ $line['qty'] }}
                        </div>
                    </div>
                    <div class="flex items-center gap-1">
                        <button wire:click="decrementQty({{ $line['product']->id }})" class="w-7 h-7 rounded border">−</button>
                        <span class="w-8 text-center font-mono text-sm">{{ $line['qty'] }}</span>
                        <button wire:click="incrementQty({{ $line['product']->id }})" class="w-7 h-7 rounded border">+</button>
                    </div>
                    <div class="w-24 text-right font-mono text-sm">Rp {{ number_format($line['subtotal'], 0, ',', '.') }}</div>
                </div>
            @endforeach
        </div>

        <div class="p-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
            <div class="flex justify-between text-sm"><span>Komisi Montir (jasa)</span>
                <span class="font-mono">Rp {{ number_format($this->serviceFeeTotal, 0, ',', '.') }}</span></div>
            <div class="flex justify-between font-bold"><span>TOTAL</span>
                <span class="font-mono text-amber-600 text-lg">Rp {{ number_format($this->totalAmount, 0, ',', '.') }}</span></div>

            <div class="grid grid-cols-2 gap-2">
                <label class="flex items-center gap-2 rounded-lg border p-2 cursor-pointer {{ $paymentMethod === 'cash' ? 'border-amber-500' : '' }}">
                    <input type="radio" wire:model="paymentMethod" value="cash"> Tunai
                </label>
                <label class="flex items-center gap-2 rounded-lg border p-2 cursor-pointer {{ $paymentMethod === 'credit' ? 'border-amber-500' : '' }}">
                    <input type="radio" wire:model="paymentMethod" value="credit"> Tempo (Kredit)
                </label>
            </div>

            @if ($paymentMethod === 'credit')
                <select wire:model="customerId" class="w-full rounded-lg border-slate-300 dark:bg-slate-900">
                    <option value="">— Pilih Pelanggan (wajib) —</option>
                    @foreach ($this->customers as $customer)
                        <option value="{{ $customer->id }}">{{ $customer->name }}</option>
                    @endforeach
                </select>
                <input type="date" wire:model="dueDate" class="w-full rounded-lg border-slate-300 dark:bg-slate-900">
                @error('customerId') <p class="text-xs text-red-500">{{ $message }}</p> @enderror
                @error('dueDate') <p class="text-xs text-red-500">{{ $message }}</p> @enderror
            @endif

            @error('cart') <p class="text-xs text-red-500">{{ $message }}</p> @enderror

            <button wire:click="checkout" wire:loading.attr="disabled"
                    class="w-full rounded-lg bg-amber-500 hover:bg-amber-400 text-black font-bold py-3 disabled:opacity-50">
                Bayar & Cetak Struk
            </button>
        </div>
    </div>

    {{-- ===== Modal struk thermal 80mm ===== --}}
    @if ($showReceipt && $lastTransaction)
        <div x-data @keydown.window.escape="window.dispatchEvent(new CustomEvent('close-receipt'))"
             class="fixed inset-0 z-50 flex items-start justify-center bg-black/60 overflow-y-auto p-6">
            <div class="bg-white text-black p-5 mt-10" style="width: 302px" id="thermal-receipt">
                <div class="text-center font-bold">{{ strtoupper(config('app.name')) }}</div>
                <div class="text-center text-xs">Bengkel Ban & Servis Otomotif</div>
                <div class="text-center text-xs">Jl. Merdeka No. 12 — 0812-3456-7890</div>
                <div class="border-t border-dashed my-2"></div>
                <div class="text-xs">No: {{ $lastTransaction->invoice_number }}</div>
                <div class="text-xs">{{ $lastTransaction->date->format('d/m/Y H:i') }}</div>
                @if ($lastTransaction->customer)
                    <div class="text-xs">Plg: {{ $lastTransaction->customer->name }}</div>
                @endif
                <div class="border-t border-dashed my-2"></div>
                @foreach ($lastTransaction->details as $d)
                    <div class="text-xs">{{ $d->product_name }}</div>
                    <div class="flex justify-between text-xs">
                        <span>{{ $d->qty }} × {{ number_format($d->price, 0, ',', '.') }}</span>
                        <span>{{ number_format($d->subtotal, 0, ',', '.') }}</span>
                    </div>
                @endforeach
                <div class="border-t border-dashed my-2"></div>
                <div class="flex justify-between font-bold"><span>TOTAL</span>
                    <span>Rp {{ number_format($lastTransaction->total_amount, 0, ',', '.') }}</span></div>
                <div class="text-xs">Bayar: {{ $lastTransaction->payment_method === 'credit' ? 'TEMPO' : 'TUNAI' }}</div>
                @if ($lastTransaction->payment_method === 'credit')
                    <div class="text-xs">Jatuh Tempo: {{ $lastTransaction->due_date->format('d/m/Y') }}</div>
                @endif
                <div class="text-center text-xs mt-3">Terima kasih 🙏</div>
            </div>
            <div class="w-full max-w-[302px] flex gap-2 mt-3">
                <button onclick="window.print()" class="flex-1 bg-amber-500 text-black font-bold py-2 rounded-lg">Cetak (80mm)</button>
                <button wire:click="closeReceipt" class="px-4 border rounded-lg text-white">Tutup</button>
            </div>
        </div>
    @endif
</div>

@push('styles')
<style>
    @media print {
        body * { visibility: hidden !important; }
        #thermal-receipt, #thermal-receipt * { visibility: visible !important; }
        #thermal-receipt { position: fixed; left: 0; top: 0; width: 80mm; }
        @page { size: 80mm auto; margin: 2mm; }
    }
</style>
@endpush
