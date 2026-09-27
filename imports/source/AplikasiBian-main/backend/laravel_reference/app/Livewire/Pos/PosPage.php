<?php

namespace App\Livewire\Pos;

use App\Models\AccountsReceivable;
use App\Models\Customer;
use App\Models\Product;
use App\Models\Transaction;
use App\Models\TransactionDetail;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Livewire\Attributes\Computed;
use Livewire\Attributes\Layout;
use Livewire\Attributes\Title;
use Livewire\Component;

#[Layout('layouts.app')]
#[Title('Kasir POS — Bengkel')]
class PosPage extends Component
{
    public string $search = '';
    public string $typeFilter = 'semua';   // semua | barang | jasa
    public array $cart = [];               // [['product_id' => int, 'qty' => int]]

    // --- checkout ---
    public string $paymentMethod = 'cash'; // cash | credit
    public ?int $customerId = null;
    public ?string $dueDate = null;

    public bool $showReceipt = false;
    public ?Transaction $lastTransaction = null;

    #[Computed]
    public function products()
    {
        return Product::query()
            ->when($this->typeFilter !== 'semua', fn ($q) => $q->where('type', $this->typeFilter))
            ->when(trim($this->search) !== '', function ($q) {
                $term = '%'.trim($this->search).'%';
                $q->where(fn ($w) => $w->where('name', 'like', $term)
                    ->orWhere('sku', 'like', $term)
                    ->orWhere('brand', 'like', $term));
            })
            ->orderBy('name')
            ->get();
    }

    #[Computed]
    public function customers()
    {
        return Customer::orderBy('name')->get();
    }

    #[Computed]
    public function cartLines(): array
    {
        $products = Product::whereIn('id', collect($this->cart)->pluck('product_id'))->get()->keyBy('id');
        return collect($this->cart)->map(fn ($line) => [
            'product' => $products[$line['product_id']],
            'qty' => $line['qty'],
            'subtotal' => $products[$line['product_id']]->selling_price * $line['qty'],
        ])->all();
    }

    #[Computed]
    public function totalAmount(): float
    {
        return (float) collect($this->cartLines)->sum('subtotal');
    }

    #[Computed]
    public function serviceFeeTotal(): float
    {
        // komisi montir untuk item jasa di keranjang
        return (float) collect($this->cartLines)
            ->filter(fn ($l) => $l['product']->type === 'jasa')
            ->sum(fn ($l) => $l['product']->service_fee * $l['qty']);
    }

    // ---- keranjang ----

    public function addToCart(int $productId): void
    {
        $product = Product::findOrFail($productId);
        foreach ($this->cart as $i => $line) {
            if ($line['product_id'] === $productId) {
                $this->incrementQty($productId);
                return;
            }
        }
        if ($product->type === 'barang' && $product->stock < 1) {
            $this->dispatch('notify', message: "Stok {$product->name} habis");
            return;
        }
        $this->cart[] = ['product_id' => $productId, 'qty' => 1];
    }

    public function incrementQty(int $productId): void
    {
        $product = Product::findOrFail($productId);
        foreach ($this->cart as $i => $line) {
            if ($line['product_id'] === $productId) {
                if ($product->type === 'barang' && $line['qty'] >= $product->stock) {
                    $this->dispatch('notify', message: "Stok {$product->name} tidak cukup (sisa {$product->stock})");
                    return;
                }
                $this->cart[$i]['qty']++;
            }
        }
    }

    public function decrementQty(int $productId): void
    {
        foreach ($this->cart as $i => $line) {
            if ($line['product_id'] === $productId) {
                if ($line['qty'] <= 1) {
                    unset($this->cart[$i]);
                } else {
                    $this->cart[$i]['qty']--;
                }
            }
        }
        $this->cart = array_values($this->cart);
    }

    public function removeFromCart(int $productId): void
    {
        $this->cart = array_values(
            array_filter($this->cart, fn ($l) => $l['product_id'] !== $productId)
        );
    }

    public function updatedPaymentMethod(string $value): void
    {
        if ($value === 'cash') {
            $this->customerId = null;
            $this->dueDate = null;
        }
    }

    // ---- checkout ----

    public function checkout(): void
    {
        $this->validate([
            'cart' => 'required|array|min:1',
            'paymentMethod' => 'required|in:cash,credit',
            'customerId' => $this->paymentMethod === 'credit' ? 'required|exists:customers,id' : 'nullable',
            'dueDate' => $this->paymentMethod === 'credit' ? 'required|date|after_or_equal:today' : 'nullable',
        ], [
            'cart.required' => 'Keranjang masih kosong.',
            'customerId.required' => 'Pelanggan wajib dipilih untuk pembayaran tempo (credit).',
            'dueDate.required' => 'Jatuh tempo wajib diisi untuk pembayaran tempo (credit).',
        ]);

        $transaction = DB::transaction(function () {
            $products = Product::whereIn('id', collect($this->cart)->pluck('product_id'))
                ->lockForUpdate()->get()->keyBy('id');

            $totalAmount = $totalCost = $totalProfit = $serviceFee = 0.0;

            $transaction = Transaction::create([
                'invoice_number' => 'INV-'.now()->format('ymd').'-'.str_pad(
                    (string) (Transaction::whereDate('date', today())->count() + 1), 4, '0', STR_PAD_LEFT
                ),
                'date' => today(),
                'customer_id' => $this->paymentMethod === 'credit' ? $this->customerId : null,
                'payment_method' => $this->paymentMethod,
                'total_amount' => 0, 'total_cost' => 0, 'total_profit' => 0, 'service_fee' => 0,
                'status' => 'completed',
                'due_date' => $this->paymentMethod === 'credit' ? $this->dueDate : null,
                'user_id' => Auth::id(),
            ]);

            foreach ($this->cart as $line) {
                $product = $products[$line['product_id']];
                $qty = $line['qty'];

                if ($product->type === 'barang' && $product->stock < $qty) {
                    $this->addError('cart', "Stok {$product->name} tidak cukup (sisa {$product->stock}).");
                    throw \Illuminate\Validation\ValidationException::withMessages([
                        'cart' => "Stok {$product->name} tidak cukup (sisa {$product->stock}).",
                    ]);
                }

                $subtotal = $product->selling_price * $qty;
                $detail = TransactionDetail::create([
                    'transaction_id' => $transaction->id,
                    'product_id' => $product->id,
                    'qty' => $qty,
                    'price' => $product->selling_price,
                    'cost_price' => $product->type === 'barang' ? $product->cost_price : 0,
                    'service_fee' => $product->type === 'jasa' ? $product->service_fee : 0,
                    'subtotal' => $subtotal,
                ]);

                if ($product->type === 'barang') {
                    $product->decrement('stock', $qty);
                    $totalCost += $product->cost_price * $qty;
                } else {
                    $serviceFee += $product->service_fee * $qty; // komisi montir
                }
                $totalAmount += $subtotal;
                $totalProfit += $detail->profit();
            }

            $transaction->update([
                'total_amount' => $totalAmount,
                'total_cost' => $totalCost,
                'total_profit' => $totalProfit,
                'service_fee' => $serviceFee,
            ]);

            // kredit (tempo) → otomatis buat piutang customer
            if ($this->paymentMethod === 'credit') {
                AccountsReceivable::create([
                    'transaction_id' => $transaction->id,
                    'customer_id' => $this->customerId,
                    'amount' => $totalAmount,
                    'due_date' => $this->dueDate,
                    'status' => 'unpaid',
                ]);
            }

            return $transaction->fresh('details.product', 'customer');
        });

        $this->lastTransaction = $transaction;
        $this->showReceipt = true; // buka modal struk thermal 80mm
        $this->reset('cart', 'customerId', 'dueDate', 'paymentMethod');
        $this->dispatch('pos-checkout-completed'); // refresh dashboard widget
    }

    public function closeReceipt(): void
    {
        $this->showReceipt = false;
        $this->lastTransaction = null;
    }

    public function render()
    {
        return view('livewire.pos.pos-page');
    }
}
